from glob import glob
import os
import cv2
from tqdm import tqdm
import numpy as np
import argparse

parser = argparse.ArgumentParser(description='Contrast Enhancement and Sharpening on the image')
parser.add_argument('source', type=str,
                    help='Source directory where the images reside')
parser.add_argument('--dest', type=str,default = 'Adjusted_Images',
                    help='Destination directory where the images will be written (default=Adjusted_Images')
args = parser.parse_args()

cwd = os.getcwd()
source_dir = os.path.join(cwd,args.source)
target_dir = os.path.join(cwd,args.dest)
flist = glob(os.path.join(source_dir,'*.jpg'))
factor = 0.25

#Create the target directory
if os.path.isdir(target_dir)==0:
    os.mkdir(target_dir)
else:
    for file in os.listdir(os.path.join('.',target_dir,)):
        if file.endswith('.jpg'):
            os.remove(os.path.join(target_dir,file))

def imadjust(img,factor):
    curr_low = np.min(img)
    curr_high = np.max(img)
    new_low = curr_low*(1-factor)
    new_high = np.minimum(1.,curr_high*(1.+factor))
    y=((img-curr_low)/(curr_high-curr_low))*(new_high-new_low)+new_low
    return y

for file in tqdm(flist):
    img = cv2.imread(file)
    #img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    I_LAB = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    L_float = I_LAB[:, :, 0].astype(float)
    L_float = imadjust(L_float/255,factor)
    gaussian_3 = cv2.GaussianBlur(L_float, (0, 0), 9.0)
    unsharp_image = cv2.addWeighted(L_float, 1.5, gaussian_3, -0.5, 0)
    I_LAB[:, :, 0] = np.clip(255 * unsharp_image, 0, 255).astype(np.uint8)
    img = cv2.cvtColor(I_LAB, cv2.COLOR_LAB2BGR)
    cv2.imwrite(os.path.join('.',target_dir,os.path.basename(file)),img)