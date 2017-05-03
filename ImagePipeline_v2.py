#!/usr/bin/env python2.7

import dicom
from dicom.errors import InvalidDicomError

import numpy as np
from PIL import Image, ImageDraw

import os,csv




class ImageTools():
    """ General Image Tools """
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
    
    
    def getContourMask(self,contourFile,width,height):
        """ Create mask from contour file (convenience method)
        :param filename: filepath to the contourfile to parse
        :param width: scalar image width
        :param height: scalar image height       
        :return: Boolean mask of shape (height, width)
        """
        
        polyCoords = self.parse_contour_file(contourFile)
        mask       = self.poly_to_mask(polyCoords,width, height)
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
        

class DicomContourReaderBase():
    """ Super class with general DicomContourReader methods
    """
       
    def getContourFileList(self,cpath):
        """ Parse Directory and collect all contour files """
        
        if not os.path.isdir(cpath):
            print "Contour path does not exist: ",cpath
            return
        
        flist =[]
        for _, _, fileList in os.walk(cpath):
            for filename in fileList:
                # check if the file is DICOM based on file extension
                if len(filename)>4 and ".txt" in filename.lower()[-4:]:  
                    flist.append(filename)
                    
        return flist
    
    
    def createContourIdMap(self,fileList):
        """Assign each contour file an ID and create Map from ID to filename.
           Assumes that Id is the same string location.
        """ 
             
        fileMap = {}
        for contFile in fileList:
            key = contFile[8:12].zfill(self._IdDigits) 
            if fileMap.has_key(key):
                print "Warning: Directory contains duplicates {} ".format(contFile)
            else:
                fileMap[ key ] = contFile
        return fileMap

    
    def getAllFilePairs(self):
        """ Collect all dicom and contour file pairs 
        :return: list of tuples (dcmFile,contourFile) 
        """
        fileList = []
        for fileId in sorted(self.contourFileMap.keys()):
            fileList.append(self.getDicomImageAndContourFiles(fileId))
        return fileList      

    

class DicomContourReader(DicomReader,DicomContourReaderBase):
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
        
        self.contourFileList = self.getContourFileList(self.contourPath)    
    
        if len(self.contourFileList) < 1:
            print "No matching contour files were found."       
        else:
            self.contourFileMap = self.createContourIdMap(self.contourFileList)
            self.contourFileIds = sorted(self.contourFileMap.keys())
            self._ncontours = len(self.contourFileIds)
            print "Found {} contour files".format(self._ncontours) 
            

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
  

class DicomContourReader2(DicomReader,DicomContourReaderBase):
    """ Parses Dicom images and corresponding i-contours and o-contours
        Only if o-contours exits, a data triple (image,i-contour,o-contour) will be returned
    """
    def __init__(self,dcmPath,contourPath):
        DicomReader.__init__(self,dcmPath)
        self.i_contourPath     = os.path.join(contourPath,'i-contours')
        self.o_contourPath     = os.path.join(contourPath,'o-contours')
        self.i_contourFileList = []
        self.o_contourFileList = []
 
        self.i_contourFileMap = {}
        self.o_contourFileMap = {}
        self.contourFileMap = {}
 
        self.contourFileIds = []
        
        self._ncontours = -1 # i_countour and o_contour exist
        
        self.getContourFileNames()
        
                
    def getContourFileNames(self):
        """ Collect all i-/o-contour files names in directory """ 
        
        self.i_contourFileList = self.getContourFileList(self.i_contourPath)
        self.o_contourFileList = self.getContourFileList(self.o_contourPath)
                          
        if len(self.i_contourFileList) < 1 or len(self.o_contourFileList) < 1:
            print "No matching contour files were found."       
        else:
            self.matchContourIdMap()
            self.contourFileIds = sorted(self.contourFileMap.keys())
            self._ncontours = len(self.contourFileIds)
            print "Found {} contour files".format(self._ncontours) 
            
                
    def matchContourIdMap(self):
        """Assign each contour file an ID and create Map from ID to filename.
           This contour Id matches i-contours and o-contours and the corresponding Dicom image Id.
           Assumes that Id is the same string location.
        """ 
        
        # get IDs for both contours
        self.i_contourFileMap = self.createContourIdMap(self.i_contourFileList)
        self.o_contourFileMap = self.createContourIdMap(self.o_contourFileList)
        
        # match contours        
        for key in self.o_contourFileMap.keys():
            if not self.i_contourFileMap.has_key(key):
                print "Warning: no contour match for ",self.o_contourFileMap[key]
            else:
                self.contourFileMap[key]= (self.i_contourFileMap[key],self.o_contourFileMap[key])


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
            i_contFile, o_contFile = self.contourFileMap[fileId]
            i_contFile   = os.path.join(self.i_contourPath,i_contFile)
            o_contFile   = os.path.join(self.o_contourPath,o_contFile)
            
            return (dcmFile,i_contFile,o_contFile)
      
                
    def getDicomImageAndMask(self,fileId):
        """ Get a single dicom image and mask from a contour file
        :fileId: string 
        :return: (dcmImage,dcmMask)
        """
                    
        (dcmFile,i_contFile,o_contFile)   = self.getDicomImageAndContourFiles(fileId)
        
        if dcmFile==None or i_contFile==None or o_contFile==None:
            return None,None,None
  
        dcmData = self.parse_dicom_file(dcmFile)
        i_mask  = self.getContourMask(i_contFile,dcmData['width'], dcmData['height'])
        o_mask  = self.getContourMask(o_contFile,dcmData['width'], dcmData['height'])

        return (dcmData['pixel_data'],i_mask,o_mask)  



class ImagePipelineBase(ImageTools):
    """ Image Pipeline Base class with general methods"""

    def read_link_file(self):
        """ import the link file """
        
        try:
            with open(self.linkFile, "r") as csvfile:
                reader = csv.reader(csvfile)
                next(reader, None)  # skip the headers
                for row in reader:
                    if len(row)==2: 
                        self.linkDict[row[0]] = row[1]
                    else:
                        print "Warning: unknown format"
        except IOError as err:
            print "Error: ", err.args, self.linkFile
            return
    
    
    def resetBatchOrder(self):
        """ Reset or initialize batch order and reshuffle"""
        self.batchStart= 0
        self.batchEnd  = self.batchStart+self.batchSize
        
        if len(self.dataIndex)==0:
            self.dataIndex = range(self._ndata)
        
        np.random.shuffle(self.dataIndex )
        
    
    def getNextBatchIndices(self):
        """ Create new set of data indeces for new batch of files"""
        
        if self.batchStart == None:
            self.resetBatchOrder()
        else:   
            # increment
            self.batchStart += self.batchSize
            self.batchEnd   += self.batchSize
            
            if self.batchEnd>self._ndata:
                self.resetBatchOrder()

        
        return self.dataIndex[self.batchStart:self.batchEnd]



    
class ImagePipeline(ImageTools,ImagePipelineBase):
    """ Image Pipeline for dicom image"""
    def __init__(self,dcmPath,contourPath,linkFile):
        
        self.dcmPath  = dcmPath
        self.contPath = contourPath
        self.linkFile = linkFile
        self.linkDict = {}
        
        self.allFilePairs = []
        self._ndata = -1
        
        self.imaHeight =256
        self.imaWidth  =256
        
        self.dataIndex = []
        self.batchStart = None # including
        self.batchEnd  = None  # excluding 
        self.batchSize = 8
        
        self.read_link_file()
        self.getAllFiles()        
        
    def getAllFiles(self):
        """ Read all files"""
        
        for key in sorted(self.linkDict.keys()):
            
            dcmDir  = os.path.join(self.dcmPath, key )
            contDir = os.path.join(self.contPath, self.linkDict[key],'i-contours')
            
            if not (os.path.isdir(dcmDir) and os.path.isdir(contDir)):
                print "Warning: invalid directories ", dcmDir, contDir
                continue
                
            dc = DicomContourReader(dcmDir,contDir)
            self.allFilePairs += dc.getAllFilePairs()
            
            self._ndata = len(self.allFilePairs)
        print "Total # files: {}".format(self._ndata)
                
    
    def getNextBatch(self):
        """ Get new batch of images and masks"""
        
        # get new data indices for next batch
        batchIdx = self.getNextBatchIndices()
        
        # initialize image and mask tensors for batches
        batchDim   = (self.batchSize, self.imaHeight, self.imaWidth)

        imaBatch = np.zeros(batchDim)
        maskBatch = np.zeros(batchDim,dtype=bool)
        
        for k in range(len(batchIdx)):
            
            idx = self.dataIndex[batchIdx[k]]
            dcmFile, contFile = self.allFilePairs[ idx ]
            
            # dicom
            dcmData = self.parse_dicom_file(dcmFile)
            
            if dcmData['height']!=self.imaHeight or dcmData['width']!=self.imaWidth:
                print "Error: image format don't match"
                return
            
            imaBatch[k] = dcmData['pixel_data']
            
            # contour
            maskBatch[k] = self.getContourMask(contFile,self.imaWidth, self.imaHeight)

            #polyCoords   = self.parse_contour_file(contFile)
            #maskBatch[k] = self.poly_to_mask(polyCoords,self.imaWidth, self.imaHeight)

           
        return imaBatch, maskBatch


class ImagePipeline2(ImageTools,ImagePipelineBase):
    """ Image Pipeline for dicom image"""
    def __init__(self,dcmPath,contourPath,linkFile):
        
        self.dcmPath  = dcmPath
        self.contPath = contourPath
        self.linkFile = linkFile
        self.linkDict = {}
        
        self.allFilePairs = []
        self._ndata = -1
        
        self.imaHeight =256
        self.imaWidth  =256
        
        self.dataIndex = []
        self.batchStart = None # including
        self.batchEnd  = None  # excluding 
        self.batchSize = 8
        
        self.read_link_file()
        self.getAllFiles()        
       
        
    def getAllFiles(self):
        """ Read all files"""
        
        for key in sorted(self.linkDict.keys()):
            
            dcmDir  = os.path.join(self.dcmPath, key )
            contDir = os.path.join(self.contPath, self.linkDict[key])
            
            print key, dcmDir, contDir
            
            if not (os.path.isdir(dcmDir) and os.path.isdir(contDir)):
                print "Warning: invalid directories ", dcmDir, contDir
                continue
            
            # get all i-/o-contours
            dc = DicomContourReader2(dcmDir,contDir)
            self.allFilePairs += dc.getAllFilePairs()
            self._ndata = len(self.allFilePairs)
                        
        print "Total # files: {}".format(self._ndata)
                       
    
    def getNextBatch(self):
        """ Get new batch of images and masks"""
        
        # get new data indeces for next batch
        batchIdx = self.getNextBatchIndices()
        
        # initialize image and mask tensors for batches
        batchDim   = (self.batchSize, self.imaHeight, self.imaWidth)
        imaBatch   = np.zeros(batchDim)
        i_maskBatch = np.zeros(batchDim,dtype=bool)
        o_maskBatch = np.zeros(batchDim,dtype=bool)
        
        for k in range(len(batchIdx)):
            
            idx = self.dataIndex[batchIdx[k]]
            dcmFile,i_contFile,o_contFile = self.allFilePairs[ idx ]
            
            # dicom
            dcmData = self.parse_dicom_file(dcmFile)
            
            if dcmData['height']!=self.imaHeight or dcmData['width']!=self.imaWidth:
                print "Error: image format don't match"
                return
            
            imaBatch[k] = dcmData['pixel_data']
            
            # i-/o-contour
            i_maskBatch[k] = self.getContourMask(i_contFile,self.imaWidth, self.imaHeight)
            o_maskBatch[k] = self.getContourMask(o_contFile,self.imaWidth, self.imaHeight)
           
        return imaBatch, i_maskBatch, o_maskBatch
    
    def getAllData(self):
        """ Get all images and masks"""
                
        # initialize image and mask tensors for batches
        dataDim   = (self._ndata, self.imaHeight, self.imaWidth)
        ima    = np.zeros(dataDim)
        i_mask = np.zeros(dataDim,dtype=bool)
        o_mask = np.zeros(dataDim,dtype=bool)
        
        for idx in range(self._ndata):
            
            dcmFile, i_contFile, o_contFile = self.allFilePairs[ idx ]
            
            # dicom
            dcmData = self.parse_dicom_file(dcmFile)
            
            if dcmData['height']!=self.imaHeight or dcmData['width']!=self.imaWidth:
                print "Error: image format don't match"
                return
            
            ima[idx] = dcmData['pixel_data']
            
            # i-/o-contour
            i_mask[idx] = self.getContourMask(i_contFile,self.imaWidth, self.imaHeight)
            o_mask[idx] = self.getContourMask(o_contFile,self.imaWidth, self.imaHeight)
           
        return ima, i_mask, o_mask
         
            
                                   

if __name__ == "__main__":
    main()
