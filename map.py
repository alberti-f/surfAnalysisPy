#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Mar 22 09:15:59 2019

@author: switt, jdiedrichsen
"""

import numpy as np
import os
import sys
import re
import pathlib
import subprocess
import nibabel as nb
import warnings
import matplotlib.pyplot as plt
import nitools as nt

def reslice_fs_to_wb(subjName,subjDir,outDir,atlasDir,\
                 smoothing=1,surfFiles=["white","pial","inflated"],\
                 curvFiles=["curv","sulc","area"],hemisphere=[0,1],\
                 alignSurf=[1,1,1],resolution="32k"):

    """
    Resamples a registered subject surface from freesurfer average to the new
    symmetric fs_LR_32 surface, standard in workbench.  
    This allows things to happen exactly in atlas space - each vertex number
    corresponds exactly to a anatomical location. 
    For more information, see: 
    https://wiki.humanconnectome.org/download/attachments/63078513/Resampling-FreeSurfer-HCP_5_8.pdf

    INPUT: 
        subjName (string): 
            Subject name 
        subjDir (string): 
            Path to freesurfer's SUBJECT_DIR (or location of freesurfer output)
        outDir (string): 
            Path to where new resampled files will be written (outDir/subjName)
    
    OPTIONAL: 
        hemisphere (array): 
            Resample left, right, or both hemispheres? (0=left, 1=right) 
            DEFAULT = [0,1]
        alignSurf (array):
            Shift the surface to correct for freesurfer convention? 
            DEFAULT = [1,1,1] 
        surfFiles (list): 
            Surface files to be resampled. 
            DEFAULT = [".white",".pial",".inflated"]
        curvFiles (list): 
            Curvature files to be resampled. 
            DEFAULT = [".curv",".sulc",".area"]
        resolution (string): 
            Resolution can be either set to '164k' or '32k'. 
            DEFAULT =  "32k"
        
    OUTPUT:
        Resampled surfaces (gifti files)
    """
    
    #BASE_DIR = pathlib.Path('surfAnalysisPy').resolve()
    #atlasDir = BASE_DIR.joinpath('standard_mesh')
    
    
    hemisphere = np.array(hemisphere)
    alignSurf = np.array(alignSurf)
    
    
    structName = ["left","right"]
    hem = ["lh","rh"]
    Hem = ["L","R"]
    
    currentDirectory = os.getcwd()
    freesurferAverageSurfaceDirectory = os.path.join(os.getenv("FREESURFER_HOME"),"average","surf")
    
    if not subjDir:
        subjDir = os.getenv("SUBJECTS_DIR")
    
    # Read in freesurfer version
    freesurferVersionFile = os.path.join(os.getenv("FREESURFER_HOME"),"build-stamp.txt") 
    f = open(freesurferVersionFile, 'r')
    freesurferVersionString = f.readline()
    f.close()
    freesurferVersionString = freesurferVersionString.replace('-v',' ')
    freesurferVersionString = re.split('[ -F]+', freesurferVersionString)
    freesurferVersion = freesurferVersionString[5]
    
    # Create new output directory for subject
    subjOutDir = os.path.join(outDir,subjName)
    if not os.path.isdir(subjOutDir):
        os.mkdir(subjOutDir)
     
    numSurfFiles = len(surfFiles)
    numCurvFiles = len(curvFiles)
    os.chdir(os.path.join(subjDir,subjName,"surf"))
    
    # Figure out the shifting of coordinate systems:
    # Freesurfer uses vertex coordinates in respect to
    # the center of the 256x256x256 image, independent
    # of the real zero point in the original image.
    # vox2surfTransformMatrix: Transform of voxels in 256x256 image to surface vertices
    # vox2spaceTransformMatrix: Transform of voxel to subject space

    anatFile = os.path.join(subjDir,subjName,"mri","brain.mgz")
    mriInfoVox2RasTkrProcess = subprocess.run(["mri_info", anatFile, "--vox2ras-tkr"],\
                         stdout=subprocess.PIPE,stderr=subprocess.PIPE).\
                         stdout.decode('utf-8').split()
    mriInfoVox2RasTkrProcessOutput = np.array(list(map(float,mriInfoVox2RasTkrProcess)))
    vox2surfTransformMatrix = mriInfoVox2RasTkrProcessOutput.reshape(-1,4)


    mriInfoVox2RasProcess = subprocess.run(["mri_info", anatFile, "--vox2ras"],\
                       stdout=subprocess.PIPE,stderr=subprocess.PIPE).\
                       stdout.decode('utf-8').split()
    mriInfoVox2RasProcessOutput = np.array(list(map(float,mriInfoVox2RasProcess)))
    vox2spaceTransformMatrix = mriInfoVox2RasProcessOutput.reshape(-1,4)
    surf2spaceTransformMatrix = np.matmul(vox2spaceTransformMatrix,np.linalg.inv(vox2surfTransformMatrix))
    
    # Transform the surfaces from the two hemispheres
    for h in hemisphere:
        #Convert regSphere
        regSphere = '.'.join((hem[h],"sphere.reg.surf.gii"))

        subprocess.call(["mris_convert", ('.'.join((hem[h],"sphere.reg"))),regSphere])
        
    # Transform all the surface files
        for i in range(numSurfFiles):
            # Set up file names
            fileName = '.'.join((hem[h],surfFiles[i],"surf.gii"))
            
            if len(subjName) == 0:
                surfGiftiFileName = os.path.join(subjOutDir,('.'.join((Hem[h],surfFiles[i],resolution,'surf.gii'))))
            else:
                surfGiftiFileName = os.path.join(subjOutDir,('.'.join((subjName,Hem[h],surfFiles[i],resolution,'surf.gii'))))
                
            atlasName = os.path.join(atlasDir,"resample_fsaverage",\
                                      (''.join(("fs_LR-deformed_to-fsaverage.",\
                                                Hem[h],".sphere.",resolution,"_fs_LR.surf.gii"))))
            

            subprocess.run(["mris_convert", ('.'.join((hem[h],surfFiles[i]))),fileName])
            

            subprocess.run(["wb_command", "-surface-resample",\
                             fileName,regSphere,atlasName,\
                             "BARYCENTRIC",surfGiftiFileName])
            
            surfGifti = nb.load(surfGiftiFileName)
            
            if (alignSurf[i]):
                [surfGifti.darrays[0].coordsys.xform[:,0],surfGifti.darrays[0].coordsys.xform[:,1],\
                 surfGifti.darrays[0].coordsys.xform[:,2]]=\
                 nt.affine_transform(surfGifti.darrays[0].\
                 coordsys.xform[:,0],surfGifti.darrays[0].coordsys.xform[:,1],\
                 surfGifti.darrays[0].coordsys.xform[:,2],surf2spaceTransformMatrix)
                
            nb.save(surfGifti,surfGiftiFileName)
            
    # Transform all the curvature files
        for i in range(numCurvFiles):
            # Set up file names
            fileName = '.'.join((hem[h],curvFiles[i],"shape.gii"))
            if len(subjName) == 0:
                curvGiftiFileName = os.path.join(subjOutDir,('.'.join((Hem[h],curvFiles[i],resolution,"shape.gii"))))
            else:
                curvGiftiFileName = os.path.join(subjOutDir,('.'.join((subjName,Hem[h],curvFiles[i],resolution,"shape.gii"))))
            atlasName = os.path.join(atlasDir,"resample_fsaverage",\
                                     (''.join(("fs_LR-deformed_to-fsaverage.",\
                                               Hem[h],".sphere.",resolution,"_fs_LR.surf.gii"))))
                
            subprocess.run(["mris_convert", "-c", ('.'.join((hem[h],curvFiles[i]))),\
                            ('.'.join((hem[h],surfFiles[0]))), fileName])
            subprocess.run(["wb_command", "-metric-resample",\
                             fileName, regSphere, atlasName, "BARYCENTRIC", curvGiftiFileName])           

def vol_to_surf(volumes, whiteSurfGifti, pialSurfGifti,
            ignoreZeros=0, excludeThres=0, depths=[0,0.2,0.4,0.6,0.8,1.0],
            stats='nanmean'):
    """
    Maps volume data onto a surface, defined by white and pial surface.
    Function enables mapping of volume-based data onto the vertices of a
    surface. For each vertex, the function samples the volume along the line
    connecting the white and gray matter surfaces. The points along the line
    are specified in the variable 'depths'. default is to sample at 5
    locations between white an gray matter surface. Set 'depths' to 0 to
    sample only along the white matter surface, and to 0.5 to sample along
    the mid-gray surface.

    The averaging across the sampled points for each vertex is dictated by
    the variable 'stats'. For functional activation, use 'mean' or
    'nanmean'. For discrete label data, use 'mode'.

    If 'exclude_thres' is set to a value >0, the function will exclude voxels that
    touch the surface at multiple locations - i.e. voxels within a sulcus
    that touch both banks. Set this option, if you strongly want to prevent
    spill-over of activation across sulci. Not recommended for voxels sizes
    larger than 3mm, as it leads to exclusion of much data.

    For alternative functionality see wb_command volumne-to-surface-mapping
    https://www.humanconnectome.org/software/workbench-command/-volume-to-surface-mapping

    @author joern.diedrichsen@googlemail.com, Feb 2019 (Python conversion: switt)

    INPUTS:
        volumes (list):
            List of filenames, or nibable.NiftiImage  to be mapped
        whiteSurfGifti (string or nibabel.GiftiImage):
            White surface, filename or loaded gifti object
        pialSurfGifti (string or nibabel.GiftiImage):
            Pial surface, filename or loaded gifti object
    OPTIONAL:
        ignoreZeros (bool):
            Should zeros be ignored in mapping? DEFAULT:  False
        depths (array-like):
            Depths of points along line at which to map (0=white/gray, 1=pial).
            DEFAULT: [0.0,0.2,0.4,0.6,0.8,1.0]
        stats (str or lambda function):
            function that calculates the Statistics to be evaluated.
            lambda X: np.nanmean(X,axis=0) default and used for activation data
            lambda X: scipy.stats.mode(X,axis=0) used when discrete labels are sampled. The most frequent label is assigned.
        excludeThres (float):
            Threshold enables the exclusion of voxels that touch the surface
            in two distinct places
            (e.g., voxels that lie in the middle of a sulcus). If a voxel projects to two separate place
            on the surface, the algorithm excludes it, if the proportion of the bigger cluster
            is smaller than the threshold. (i.e. threshold = 0.9 means that the voxel has to
            lie at least to 90% on one side of the sulcus).
            **** Currently not supported.  excludeThres is automatically reset to 0. ****
            DEFAULT: 0

    OUTPUT:
        mapped_data (numpy.array):
            A Data array for the mapped data
    """

    Vols = []
    firstGood = None
    depths = np.array(depths)

    if excludeThres != 0:
        print('Warning: excludeThres option currently not supported. Resetting excludeThres to 0.')
        excludeThres = 0

    numPoints = len(depths)

    whiteSurfGiftiImage = nb.load(whiteSurfGifti)
    pialSurfGiftiImage = nb.load(pialSurfGifti)

    c1 = whiteSurfGiftiImage.darrays[0].data
    c2 = pialSurfGiftiImage.darrays[0].data
    faces = whiteSurfGiftiImage.darrays[1].data

    numVerts = c1.shape[0]

    if c2.shape[0] != numVerts:
        sys.exit('Error: White and pial surfaces should have same number of vertices.')

    for i in range(len(volumes)):
        try:
            a = nb.load(volumes[i])
            Vols.append(a)
            firstGood = i
        except:
            print(f'File {volumes[i]} could not be opened')
            Vols.append(None)

    if firstGood is None:
        sys.exit('Error: None of the images could be opened.')

    # Get the indices for all the points being sampled
    indices = np.zeros((numPoints,numVerts,3),dtype=int)
    for i in range(numPoints):
        c = (1-depths[i])*c1.T+depths[i]*c2.T
        ijk = nt.coords_to_voxelidxs(c,Vols[firstGood])
        indices[i] = ijk.T

# indices = np.transpose(np.squeeze(np.asarray(indices)))
    # indices = indices.astype(int)


    # Case: excludeThres > 0
    # If necessary, now ensure that voxels are mapped on to continuous location
    # only on the flat map - exclude voxels that are assigned to two sides of
    # the sulcus
#    if (excludeThres>0):
#        exclude = np.zeros([np.prod(V[1].shape),1])
#        if not faces:
#            sys.exit('provide faces (topology data), so that projections should be avoided')
#        S.Tiles = faces

        # Precalculate edges for fast cluster finding
#        print('Calculating edges.')
#        S.numNodes = np.max(np.max(S.Tiles))
#        for i in range (3):
#            i1 = S.Tiles[:,i]
#            i2 = S.Tiles[:,np.remainder(i,3)+1]
#            S.Edges.append(i1,i2)
#        S.Edges = np.unique(S.Edges,axis=0)

        # Generate connectivity matrix
        # csr_matrix((data, (row_ind, col_ind)), [shape=(M, N)])
#        data = np.ones(len(S.Edges))
#        rowInd = S.Edges[:,0]
#        colInd = S.Edges[:,1]
#        M = S.numNodes
#        G = sparse.csr_matrix((data,(rowInd,colInd)),shape=(M,M))

        # Cluster the projections to the surface and exclude all voxels
        # in which the weight of the biggest cluster is not > thres
#        print('Checking projections.')
#        I = np.unique(indices[np.isfinite(indices)])
#        for i in I:

            # Calculate the weight of voxel on node
#            weight = np.sum(indices==1,1)
#            indx = np.where(weight>0)[0]

            # Check whether the nodes cluster
#            H = G[indx,indx]
#            H = H+np.transpose(H)+sparse.identity(len(H))
            # Matlab vairable translation: p=rowPerm,q=colPerm,r=rowBlock,s=colBlock
#            nb,rowPerm,colPerm,rowBlock,colBlock,coarseRowBlock,coarseColBlock = H.sparsify().btf()
#            CL = np.zeros(np.shape(indx))
#            for c in range(len(rowBlock)-1):
#                CL[rowPerm[rowBlock[c]]:rowBlock[(c+1)]-1,0]=c

#            if (np.max(CL)>1):
#                weight_cl=np.zeros([np.max(CL),1])
#                for cl in range(np.max(CL)):
#                    weight_cl[cl,0] = np.sum(weight[indx[CL==cl]])
#                [m,cl] = np.max(weight_cl)
#                if (m/np.sum(weight_cl)>excludeThres):
#                    A = indices[indx[CL!=cl],:]
#                    A[A==i] = np.nan
#                    indices[indx[CL!=cl],:] = A
#                    exclude[i] = 1
#                    print('assigned: %2.3f'.format(m/np.sum(weight_cl)))
#                else:
#                    A[A==i] = np.nan
#                    indices[indx,:] = A
#                    exclude[i] = 2
#                    print('excluded: %2.3f %d'.format(m/np.sum(weight_cl),np.max(CL)))

        # For debugging: save the volume showing the exluded voxels in current
        # directory
#        Vexcl = V[1]
#        Vexcl.set_filename = 'excl.nii'
#        nb.save(np.reshape(exclude,np.array(Vexcl.shape)),'excl.nii')

   # Read the data and map it
    data = np.zeros((numPoints,numVerts))
    mapped_data = np.zeros((numVerts,len(Vols)))
    for v,vol in enumerate(Vols):
        if vol is None:
            pass
        else:
            X = vol.get_fdata()
            if (ignoreZeros>0):
                X[X==0] = np.nan
            for p in range(numPoints):
                data[p,:] = X[indices[p,:,0],indices[p,:,1],indices[p,:,2]]
                outside = (indices[p,:,:]<0).any(axis=1) # These are vertices outside the volume
                data[p,outside] = np.nan

            # Determine the right statistics - if function - call it
            if stats=='nanmean':
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", category=RuntimeWarning)
                    mapped_data[:,v] = np.nanmean(data,axis=0)
            elif stats=='mode':
                mapped_data[:,v],_ = ss.mode(data,axis=0)
            elif callable(stats):
                mapped_data[:,v] = stats(data)

    return mapped_data
