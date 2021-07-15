import cv2
import numpy as np
from glob import glob
import os
from skimage import filters as skifilters
from scipy import ndimage
from skimage import filters
from tqdm import tqdm
import argparse

def color_constancy(img, power=6, gamma=None):
    img = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
    img_dtype = img.dtype

    if gamma is not None:
        img = img.astype('uint8')
        look_up_table = np.ones((256,1), dtype='uint8') * 0
        for i in range(256):
            look_up_table[i][0] = 255*pow(i/255, 1/gamma)
        img = cv2.LUT(img, look_up_table)

    img = img.astype('float32')
    img_power = np.power(img, power)
    rgb_vec = np.power(np.mean(img_power, (0,1)), 1/power)
    rgb_norm = np.sqrt(np.sum(np.power(rgb_vec, 2.0)))
    rgb_vec = rgb_vec/rgb_norm
    rgb_vec = 1/(rgb_vec*np.sqrt(3))
    img = np.multiply(img, rgb_vec)
    img = np.clip(img,0,255)

    img = cv2.cvtColor(np.array(img), cv2.COLOR_BGR2RGB)
    return img.astype(img_dtype)

def shades_gray(image, njet=0, mink_norm=1, sigma=1):
    """
    Estimates the light source of an input_image as proposed in:
    J. van de Weijer, Th. Gevers, A. Gijsenij
    "Edge-Based Color Constancy"
    IEEE Trans. Image Processing, accepted 2007.
    Depending on the parameters the estimation is equal to Grey-World, Max-RGB, general Grey-World,
    Shades-of-Grey or Grey-Edge algorithm.
    :param image: rgb input image (NxMx3)
    :param njet: the order of differentiation (range from 0-2)
    :param mink_norm: minkowski norm used (if mink_norm==-1 then the max
           operation is applied which is equal to minkowski_norm=infinity).
    :param sigma: sigma used for gaussian pre-processing of input image
    :return: illuminant color estimation
    :raise: ValueError
    
    Ref: https://github.com/MinaSGorgy/Color-Constancy
    """
    gauss_image = filters.gaussian(image, sigma=sigma, multichannel=True)
    
    if njet == 0:
        deriv_image = [gauss_image[:, :, channel] for channel in range(3)]
    else:   
        if njet == 1:
            deriv_filter = filters.sobel
        elif njet == 2:
            deriv_filter = filters.laplace
        else:
            raise ValueError("njet should be in range[0-2]! Given value is: " + str(njet))     
        deriv_image = [np.abs(deriv_filter(gauss_image[:, :, channel])) for channel in range(3)]
    for channel in range(3):
        deriv_image[channel][image[:, :, channel] >= 255] = 0.
    if mink_norm == -1:  
        estimating_func = np.max 
    else:
        estimating_func = lambda x: np.power(np.sum(np.power(x, mink_norm)), 1 / mink_norm)
    illum = [estimating_func(channel) for channel in deriv_image]
    som   = np.sqrt(np.sum(np.power(illum, 2)))
    illum = np.divide(illum, som)
    return illum


def correct_image(image, illum):
    """
    Corrects image colors by performing diagonal transformation according to 
    given estimated illumination of the image.
    :param image: rgb input image (NxMx3)
    :param illum: estimated illumination of the image
    :return: corrected image
    
    Ref: https://github.com/MinaSGorgy/Color-Constancy
    """
    correcting_illum = illum * np.sqrt(3)
    corrected_image = image / 255.
    for channel in range(3):
        corrected_image[:, :, channel] /= correcting_illum[channel]
    return np.clip(corrected_image, 0., 1.)



##MAIN CODE##
parser = argparse.ArgumentParser(description='Apply color_constancy to the given directory of image')
parser.add_argument('source', type=str,
                    help='Source directory where the images reside')
parser.add_argument('--dest', type=str,default = 'Adjusted_Images',
                    help='Destination directory where the images will be written (default=Adjusted_Images')
parser.add_argument('-cc','--colorConstacy', action='store_false')
parser.add_argument('-rgbc','--mRGB', action='store_true')
parser.add_argument('-gc','--GrayWorld', action='store_true')
parser.add_argument('--verbose', help='Print more data',
    action='store_true')
args = parser.parse_args()

cwd = os.getcwd()
source_dir = os.path.join(cwd,args.source)
target_dir = os.path.join(cwd,args.dest)
flist = glob(os.path.join(source_dir,'*.jpg'))

#Create the target directory
if os.path.isdir(target_dir)==0:
    os.mkdir(target_dir)
else:
    for file in os.listdir(os.path.join('.',target_dir,)):
        if file.endswith('.jpg'):
            os.remove(os.path.join(target_dir,file))

for file in flist: 
    img = cv2.imread(file)
    if args.colorConstacy:
        cc = color_constancy(img,power = 6,gamma=1.2)
        cv2.imwrite(os.path.join('.',target_dir,os.path.basename(file))[:-4]+'_CC.jpg',cc)
    img = img.astype('float32')
    if args.mRGB:
        mx  = correct_image(img, shades_gray(img, njet=0, mink_norm=-1, sigma=15))  # MaxRGB Constancy
        cv2.imwrite(os.path.join('.',target_dir,os.path.basename(file))[:-4]+'_mRGB.jpg',(mx*255).astype('uint8'))
    if args.GrayWorld:
        gw  = correct_image(img, shades_gray(img, njet=0, mink_norm=+1, sigma=15))  # Gray World Constancy  
        cv2.imwrite(os.path.join('.',target_dir,os.path.basename(file))[:-4]+'_GC.jpg',(gw*255).astype('uint8'))

