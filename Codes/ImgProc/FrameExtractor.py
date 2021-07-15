## Read the list of video files from a csv and extract frames to an output folder
# CSV file is one column, first column being "Filename"
import glob, cv2, os
import numpy as np
import matplotlib as plt
import pandas as pd
import os.path as pt

#Fram extractor Function 
def FrameExtractor(video,dest):

    [dirName,fname] = pt.split(video)
    [fname,ext] = pt.splitext(fname)
    
    dest = pt.join(dest,fname)
    cap = cv2.VideoCapture(video)
    
    if pt.isdir(dest)==0:
        os.mkdir(dest)
    
    print(fname)
    
    #read a frame from the video
    counter = 1
    ret, frame = cap.read()
    while(ret):
        # Our operations on the frame come here
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        filename = ("{:0>5d}.jpg".format(counter))
        print(pt.join(dest,filename))
        cv2.imwrite(pt.join(dest,filename),gray)

        #read a frame from the video
        ret, frame = cap.read()
        counter = counter+1        
        

    # When everything done, release the capture
    cap.release()

## Main Code Starts Here

# Get the list of images.
videos = pd.read_csv('./ProcessList.csv')
videosList = videos['Filename']

#Create destination folder
destFolder = './Output'
if pt.isdir(destFolder)==0:
    os.mkdir(destFolder)

for video in videosList:
    FrameExtractor(video,destFolder)