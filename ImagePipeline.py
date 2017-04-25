#!/usr/bin/env python2.7

import dicom
from dicom.errors import InvalidDicomError

import numpy as np
from PIL import Image, ImageDraw

import os,csv

class ImageTools():
	""" Collection of image tools"""

    def parse_contour_file(self,filename):
        """Parse the given contour filename

        :param filename: filepath to the contourfile to parse
        :return: list of tuples holding x, y coordinates of the contour
        """

        coords_lst = []

        with open(filename, 'r') as infile:
            for line in infile:
                coords = line.strip().split()

                x_coord = float(coords[0])
                y_coord = float(coords[1])
                coords_lst.append((x_coord, y_coord))

        return coords_lst

    def parse_dicom_file(self,filename):
        """Parse the given DICOM filename

        :param filename: filepath to the DICOM file to parse
        :return: dictionary with DICOM image data
        """
        try:
            dcm = dicom.read_file(filename)
        except IOError as err:
            print 'Error:', os.strerror(err.errno),', file: ', filename
            return None
        
        try:
            dcm_image = dcm.pixel_array
            
            # image dimensions
            dcm_height = dcm.Rows
            dcm_width  = dcm.Columns

            # scale image
            try:
                intercept = dcm.RescaleIntercept
            except AttributeError:
                intercept = 0.0
            try:
                slope = dcm.RescaleSlope
            except AttributeError:
                slope = 0.0

            if intercept != 0.0 and slope != 0.0:
                dcm_image = dcm_image*slope + intercept

            dcm_dict = {'pixel_data' : dcm_image,
                        'height'     : dcm_height,
                        'width'      : dcm_width
                       }
            return dcm_dict
        except InvalidDicomError:
            return None
    

    def poly_to_mask(self,polygon, width, height):
        """Convert polygon to mask

        :param polygon: list of pairs of x, y coords [(x1, y1), (x2, y2), ...]
         in units of pixels
        :param width: scalar image width
        :param height: scalar image height
        :return: Boolean mask of shape (height, width)
        """

        # http://stackoverflow.com/a/3732128/1410871
        img = Image.new(mode='L', size=(width, height), color=0)
        ImageDraw.Draw(img).polygon(xy=polygon, outline=0, fill=1)
        mask = np.array(img).astype(bool)
        return mask



class DicomReader(ImageTools):
	""" Parses and reads dicom images in a dicom directory dcmPath"""
    def __init__(self,dcmPath):
        self.dcmPath = dcmPath
        self.dcmFileList = []# list of all file names 
        self.dcmFileMap = {} # dictionary from file id to file name
        
        self._nima = -1      # number of images
        self._IdDigits= 4    # id digits for file id
        
        self.getDicomFileNames()
    
    def getDicomFileNames(self):
        """ Collect all Dicom files names in directory """ 
        
        if not os.path.isdir(self.dcmPath):
            print "Image path does not exist"
            return
        
        #for dirName, subdirList, fileList in os.walk(self.dcmPath):
        for _, _, fileList in os.walk(self.dcmPath):
            for filename in fileList:
                # check if the file is DICOM based on file extension
                if len(filename)>4 and ".dcm" in filename.lower()[-4:]:  
                    self.dcmFileList.append(filename)
        
        if len(self.dcmFileList)< 1:
            print "No matching dicom files were found."
        else:
            self.createFileIdMap()
            self.dcmFileIds = sorted(self.dcmFileMap.keys())
            self._nima = len(self.dcmFileIds)
 
            print "Found {} dcm images".format(self._nima)
     
    def createFileIdMap(self):
        """assign each file an ID and create Map from ID to filename""" 
        
        for dcmFile in self.dcmFileList:
            key = dcmFile[:-4].zfill(self._IdDigits) 
            if self.dcmFileMap.has_key(key):
                print "Warning: Directory contains duplicates {} ".format(dcmFile)
            else:
                self.dcmFileMap[ key ] = dcmFile
                    
    def getDicomImageFile(self,fileId):
        """ Get a single dicom image file """
        
        if not self.dcmFileMap.has_key(fileId):
            print "Unknown dicom file ID {}".format(fileId)
            return None
        else:
            return os.path.join(self.dcmPath,self.dcmFileMap[fileId])

    def getDicomImage(self,fileId):
        """ Get a single dicom image """
        
        dcmFile = self.getDicomImageFile(fileId)
        if dcmFile==None:
            return None
        else:
            return self.parse_dicom_file(dcmFile)          
  


class DicomContourReader(DicomReader):
	""" Parses Dicom images and corresponding contours"""
    def __init__(self,dcmPath,contourPath):
        DicomReader.__init__(self,dcmPath)
        self.contourPath     = contourPath
        self.contourFileList = []
        self.contourFileMap = {}
        self.contourFileIds = []
        
        self._ncontours = -1
        
        self.getContourFileNames()
                
    def getContourFileNames(self):
        """ Collect all contour files names in directory """ 
        
        if not os.path.isdir(self.contourPath):
            print "Contour path does not exist"
            return
        
        for _, _, fileList in os.walk(self.contourPath):
            for filename in fileList:
                # check if the file is DICOM based on file extension
                if len(filename)>4 and ".txt" in filename.lower()[-4:]:  
                    self.contourFileList.append(filename)
                    
        self._ncontours = len(self.contourFileList)
        
        if len(self.contourFileList) < 1:
            print "No matching contour files were found."       
        else:
            self.createContourIdMap()
            self.contourFileIds = sorted(self.contourFileMap.keys())
            self._ncontours = len(self.contourFileIds)
            print "Found {} contour files".format(self._ncontours) 
            
    def createContourIdMap(self):
        """Assign each contour file an ID and create Map from ID to filename.
           This contour Id matches the corresponding Dicom image Id.
           Assumes that Id in the same string location.
        """ 
        
        for contFile in self.contourFileList:
            key = contFile[8:12].zfill(self._IdDigits) 
            if self.contourFileMap.has_key(key):
                print "Warning: Directory contains duplicates {} ".format(contFile)
            else:
                self.contourFileMap[ key ] = contFile

    def getDicomImageAndContourFiles(self,fileId):
        """ Get a single dicom image and a matching contour file
        :fileId: string 
        :return: (dcmFile,contourFile)
        """
        
        if not self.contourFileMap.has_key(fileId):
            print "Unknown contour File ID {}".format(fileId)
            return None,None
            
        dcmFile   = self.getDicomImageFile(fileId) 
        if dcmFile == None:
            return None,None
        else:
            contourFile   = os.path.join(self.contourPath,self.contourFileMap[fileId])
            return (dcmFile,contourFile)

        
    def getAllFilePairs(self):
        """ Collect all dicom and contour file pairs 
        :return: list of tuples (dcmFile,contourFile) 
        """
        fileList = []
        for fileId in sorted(self.contourFileMap.keys()):
            fileList.append(self.getDicomImageAndContourFiles(fileId))
        return fileList      
                
    def getDicomImageAndMask(self,fileId):
        """ Get a single dicom image and mask from a contour file
        :fileId: string 
        :return: (dcmImage,dcmMask)
        """
                    
        (dcmFile,contourFile)   = self.getDicomImageAndContourFiles(fileId)
        
        if dcmFile==None or contourFile==None:
            return None,None
  
        dcmData    = self.parse_dicom_file(dcmFile)
        polyCoords = self.parse_contour_file(contourFile)
        mask       = self.poly_to_mask(polyCoords,dcmData['width'], dcmData['height'])

        return (dcmData['pixel_data'],mask)  

if __name__ == "__main__":
    main()
