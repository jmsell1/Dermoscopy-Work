import cv2
import numpy as np
from glob import glob
import os
from skimage import filters as skifilters
from scipy import ndimage
from skimage import filters
from sklearn import preprocessing
from tqdm import tqdm
import argparse

def center(X):
    newX = X - np.mean(X, axis = 0)
    return newX

def standardize(X):
    newX = center(X)/np.std(X, axis = 0)
    return newX


def decorrelate(X):
    newX = center(X)
    cov = X.T.dot(X)/float(X.shape[0])
    # Calculate the eigenvalues and eigenvectors of the covariance matrix
    eigVals, eigVecs = np.linalg.eig(cov)
    # Apply the eigenvectors to X
    decorrelated = X.dot(eigVecs)
    return decorrelated

def whiten(img):
    img = np.asarray(img, dtype='float32').transpose(2, 0, 1)/255
    whitened = []
    for ii in range(3):#loop over color channels
        ch = img[ii] - img[ii].mean()#center the data
        ch = np.fft.fft2(ch)
        spectr = np.sqrt(np.mean(np.dot(abs(ch),abs(ch))))
        out = np.fft.ifft2(np.dot(ch,1./spectr))
        whitened.append(preprocessing.scale(np.real(out)))
    whitened = np.asarray(whitened).transpose(1,2,0)
    return np.asarray(whitened)


##MAIN CODE##
parser = argparse.ArgumentParser(description='Apply image whitening')
parser.add_argument('source', type=str,
                    help='Source directory where the images reside')
parser.add_argument('--dest', type=str,default = 'Adjusted_Images',
                    help='Destination directory where the images will be written (default=Adjusted_Images')
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
    cc = whiten(img)
    cc = (cc-cc.min())/(cc.max()-cc.min()+1e-6)
    cv2.imwrite(os.path.join('.',target_dir,os.path.basename(file)),cc*255)


