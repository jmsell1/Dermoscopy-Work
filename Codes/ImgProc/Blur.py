import os
import time
import warnings
import pyfftw
from os.path import join
from threading import Thread
import pyfftw, multiprocessing
import tifffile as tiff
from glob import glob
from tqdm import tqdm
import cv2
import numpy as np
import scipy.signal
import scipy.sparse
from PIL import Image, ImageDraw
from numba import jit, float32
from scipy import interpolate
from sympy import *
from sympy.matrices import *
import argparse

def gaussian_alpha(size,mu = 0, sigma = 1):
    # Initializing value of x-axis and y-axis
    # in the range -1 to 1
    x, y = np.meshgrid(np.linspace(-1,1,size), np.linspace(-1,1,size))
    dst = np.sqrt(x*x+y*y)
      
    # Calculating Gaussian array
    gauss = np.exp(-( (dst-mu)**2 / ( 2.0 * sigma**2 ) ) )
    return gauss

def auto_vibrance(src):
    """
    Add some more saturation preserving the skin tones (A < 20, B < 18)
    """
    x1 = np.array([-100, -50, -20, 0, 20, 50, 100])
    y1 = np.array([100,  45, 19, 1, 19, 45, 100])
    s1 = interpolate.UnivariateSpline(x1, y1)

    x2 = np.array([-100, -50, -20, 0, 20, 50, 100])
    y2 = np.array([100, 50, 20, 1, 20, 50, 100])
    s2 = interpolate.UnivariateSpline(x2, y2)

    src.A = src.A * s2(src.A) / s1(src.A)
    src.B = src.B * s2(src.B) / s1(src.B)

    return src

def disc_blur(x):
    half = [1 / (np.pi * x ** 2) for x in range(1, int(x / 2) + 1)]
    return half


def lens_blur(size):
    window = disc_blur(size)
    kern = np.outer(window, window)
    kern = kern / kern.sum()
    return kern


def uniform_kernel(size):
    kern = np.ones((size, size))
    kern /= np.sum(kern)
    return kern


def gaussian_kernel(radius, std):
    window = scipy.signal.gaussian(radius, std=std)
    kern = np.outer(window, window)
    kern = kern / kern.sum()
    return kern


def kaiser_kernel(radius, beta):
    window = np.kaiser(radius, beta)
    kern = np.outer(window, window)
    kern = kern / kern.sum()
    return kern


def poisson_kernel(radius, tau):
    window = scipy.signal.exponential(radius, tau=tau)
    kern = np.outer(window, window)
    kern = kern / kern.sum()
    return kern


def bilateral_differences(source, filtered_image, W, thread, radius, pad, std_i, std_s):
    """
    Perform the bilateral differences and weighting on the (i, j) neighbour.
    For multithreading purposes
    This provides the loop to run inside each thread.
    """

    for (i, j) in thread:
        neighbour = pad[radius + i: radius + i + source.shape[0],
                        radius + j: radius + j + source.shape[1]]

        distance = np.sqrt(i * i + j * j)

        gi = gaussian((neighbour - source), std_i)
        gs = gaussian(distance, std_s)

        w = gi * gs
        filtered_image += neighbour * w
        W += w


@jit(cache=True)
def bilateral_filter(source, radius, std_i, std_s, parallel=1):
    """
    Optimized parallel Cython function to perform bilateral filtering
    For multithreading purposes
    This provides the thread splitting and returns the filtered image
    """

    filtered_image = np.zeros_like(source).astype(float)
    pad = np.pad(source, (radius, radius), mode="symmetric")
    W = np.zeros_like(source).astype(float)

    num_threads = os.cpu_count()

    iseq = range(-radius, radius + 1)
    jseq = iseq

    combi = np.transpose([np.tile(iseq, len(jseq)),
                                    np.repeat(jseq, len(iseq))])

    chunks = np.array_split(combi, num_threads)

    processing_threads = []

    for chunk in chunks:
        if parallel == 0:
            bilateral_differences(source, filtered_image,
                                  W, chunk, radius, pad, std_i, std_s)

        else:
            p = Thread(target=bilateral_differences,
                       args=(source, filtered_image, W, chunk, radius, pad, std_i, std_s))
            p.start()
            processing_threads.append(p)

    if parallel == 1:
        for thread in processing_threads:
            thread.join()

    return np.divide(filtered_image, W)


@jit(cache=True)
def bessel_blur(src, radius, amount):
    """
    Blur filter using Bessel function
    """
    if src.ndim == 2:
        # gray image
        src = scipy.signal.convolve2d(src,
                                  kaiser_kernel(radius, amount),
                                  mode="same",
                                  boundary="symm"
                                  )
    elif src.shape[2] == 3:
        # rgb image
        # for each channel:
        for i in range(3):
            src[:, :, i] = scipy.signal.convolve2d(src[:, :, i],
                                  kaiser_kernel(radius, amount),
                                  mode="same",
                                  boundary="symm"
                                  )
    
    return src


@jit(cache=True)
def gaussian_blur(src, radius, amount):
    """
    Blur filter using the Gaussian function
    """
    if src.ndim == 2:
        # gray image
        src = scipy.signal.convolve2d(src,
                                  gaussian_kernel(radius, amount),
                                  mode="same",
                                  boundary="symm"
                                  )
    elif src.shape[2] == 3:
        # rgb image
        # for each channel:
        for i in range(3):
            src[:, :, i] = scipy.signal.convolve2d(src[:, :, i],
                                  gaussian_kernel(radius, amount),
                                  mode="same",
                                  boundary="symm"
                                  )
    
    return src
    

def focus_blur(src,radius = 15, blur_amount = 1,gauss_sigma = 0.25):
    alpha = 1-gaussian_alpha(512,sigma = gauss_sigma, mu = 0)
    alpha = np.clip(alpha-0.3,0,1)
    alpha -= np.min(alpha)
    alpha /= np.max(alpha)    
    src_blur = bessel_blur(src.copy(), radius,blur_amount)
    res = src + (src - src_blur) * 0.5
    if src.ndim == 2:
        res = res * (1.0 - alpha) + src_blur * alpha
    elif src.shape[2] == 3:
        for i in range(3):
            res[:,:,i] = res[:,:,i] * (1.0 - alpha) + src_blur[:,:,i] * alpha#img + (img - img2) * 0.7
    return res


@jit(cache=True)
def USM(src, radius, strength, amount, method="bessel"):
    """
    Unsharp mask using Bessel or Gaussian blur
    """

    blur = {"bessel": bessel_blur, "gauss": gaussian_blur}

    src = src + (src - blur[method](src, radius, strength)) * amount

    return src


@jit(cache=True)
def overlay(upx, lpx):
    """
    Overlay blending mode between 2 layers : upx (top) and lpx (bottom)
    """

    return [lpx < 50] * (2 * upx * lpx / 100) + [lpx > 50] * \
        (100 - 2 * (100 - upx) * (100 - lpx) / 100)


@jit(cache=True)
def blending(upx, lpx, type):
    """
    Expose the blending modes to Python code
    upx : top layer
    dpx: bottom layer
    """

    types = {"overlay": overlay}

    return types[type](upx, lpx)


##Main Code Starts here##

parser = argparse.ArgumentParser(description='Apply blurring on the images')
parser.add_argument('source', type=str,
                    help='Source directory where the images reside')
parser.add_argument('--dest', type=str,default = 'Adjusted_Images',
                    help='Destination directory where the images will be written (default=Adjusted_Images')
args = parser.parse_args()

cwd = os.getcwd()
source_dir = os.path.join(cwd,args.source)
target_dir = os.path.join(cwd,args.dest)
flist = glob(os.path.join(source_dir,'*.jpg'))
#Parameters of blur
radius = 15
blur_amount=1
gauss_sigma = 0.25


#Create the target directory
if os.path.isdir(target_dir)==0:
    os.mkdir(target_dir)
else:
    for file in os.listdir(os.path.join('.',target_dir,)):
        if file.endswith('.jpg'):
            os.remove(os.path.join(target_dir,file))

for file in tqdm(flist):
    img = cv2.imread(file)
    img = img.astype('float32')/255
    res = focus_blur(img,radius = radius,blur_amount=blur_amount,gauss_sigma = gauss_sigma)
    #print(os.path.join('.',target_dir,os.path.basename(file)))
    cv2.imwrite(os.path.join('.',target_dir,os.path.basename(file)),(res*255).astype(int))
    '''
    plt.imshow(np.concatenate((res,img),axis =1))
    plt.show()
    '''