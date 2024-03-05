#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
This module contains functions specific to wave data extraction and hydrodynamic calculations.
Freya Muir  - University of Glasgow
"""

import os
import math
from datetime import datetime, timedelta

import numpy as np

import geopandas as gpd
from shapely import geometry
from shapely.geometry import Point, Polygon, LineString, MultiLineString, MultiPoint
from shapely.ops import linemerge

import netCDF4

from Toolshed import Toolbox




def GetHindcastWaveData(settings, output, lonmin, lonmax, latmin, latmax):
    """
    Download command for CMEMS wave hindcast data. User supplies date range, AOI, username and password.
    
    FM, Oct 2021 (updated Aug 2023)

    Parameters
    ----------
    settings : dict
        Veg edge model settings (including user inputs).
    output : dict
        Output veg edges produced by model.
    lonmin, lonmax, latmin, latmax : float
        Bounding box coords.
    User : str
        CMEMS username.
    Pwd : str
        CMEMS password.

    """
    
    print('Downloading wave data from CMEMS ...')   
    WavePath = os.path.join(settings['inputs']['filepath'],'tides')   
    
    # DateMin = settings['inputs']['dates'][0]
    # DateMax = settings['inputs']['dates'][1]
    
    # Buffer dates from output by 3 months
    DateMin = datetime.strftime(datetime.strptime(min(output['dates']), '%Y-%m-%d')-timedelta(days=90), '%Y-%m-%d %H:%M:%S')
    DateMax = datetime.strftime(datetime.strptime(max(output['dates']), '%Y-%m-%d'), '%Y-%m-%d %H:%M:%S')
    
    # NetCDF file will be a set of rasters at different times with different wave params
    # params get pulled out further down after downloading
    WaveOutFile = 'MetO-NWS-WAV-hi_'+settings['inputs']['sitename']+'_'+DateMin[:10]+'_'+DateMax[:10]+'_waves.nc'
    
    # if file already exists, just return filepath to existing file
    if os.path.isfile(os.path.join(WavePath,WaveOutFile)):
        print('Wave data file already exists.')
        return WaveOutFile
    
    else:
        User =  input('CMEMS username: ')
        Pwd = input('CMEMS password: ')
        
        motuCommand = ('python -m motuclient --motu http://my.cmems-du.eu/motu-web/Motu --service-id NWSHELF_REANALYSIS_WAV_004_015-TDS --product-id MetO-NWS-WAV-RAN '
                       '--longitude-min '+ str(lonmin) +' --longitude-max '+ str(lonmax) +' --latitude-min '+ str(latmin) +' --latitude-max '+ str(latmax) +' '
                       '--date-min "'+ DateMin +'" --date-max "'+ DateMax +'" '
                       '--variable VHM0  --variable VMDR --variable VTPK '
                       '--out-dir '+ str(WavePath) +' --out-name "'+ str(WaveOutFile) +'" --user "'+ User +'" --pwd "'+ Pwd +'"')
        os.system(motuCommand)
        
        return WaveOutFile


def GetForecastWaveData(settings, output, lonmin, lonmax, latmin, latmax):
    """
    Download command for CMEMS wave forecast data. User supplies date range, AOI, username and password.
    
    FM, Oct 2021 (updated Aug 2023)

    Parameters
    ----------
    settings : dict
        Veg edge model settings (including user inputs).
    output : dict
        Output veg edges produced by model.
    lonmin, lonmax, latmin, latmax : float
        Bounding box coords.
    User : str
        CMEMS username.
    Pwd : str
        CMEMS password.

    """
    
    print('Downloading wave data from CMEMS ...')   
    WavePath = os.path.join(settings['inputs']['filepath'],'tides')   
    
    # DateMin = settings['inputs']['dates'][0]
    # DateMax = settings['inputs']['dates'][1]
    
    # Buffer dates from output by 1 day either side
    DateMin = datetime.strftime(datetime.strptime(min(output['dates']), '%Y-%m-%d')-timedelta(days=1), '%Y-%m-%d %H:%M:%S')
    DateMax = datetime.strftime(datetime.strptime(max(output['dates']), '%Y-%m-%d')+timedelta(days=1), '%Y-%m-%d %H:%M:%S')
    
    # NetCDF file will be a set of rasters at different times with different wave params
    # params get pulled out further down after downloading
    WaveOutFile = 'MetO-NWS-WAV-hi_'+settings['inputs']['sitename']+'_'+DateMin[:10]+'_'+DateMax[:10]+'_waves.nc'
    
    if os.path.isfile(os.path.join(WavePath, WaveOutFile)):
        return WaveOutFile
    
    else:
        User =  input('CMEMS username: ')
        Pwd = input('CMEMS password: ')
        
        motuCommand = ('python -m motuclient --motu http://nrt.cmems-du.eu/motu-web/Motu --service-id NORTHWESTSHELF_ANALYSIS_FORECAST_WAV_004_014-TDS --product-id MetO-NWS-WAV-hi '
                       '--longitude-min '+ str(lonmin) +' --longitude-max '+ str(lonmax) +' --latitude-min '+ str(latmin) +' --latitude-max '+ str(latmax) +' '
                       '--date-min "'+ DateMin +'" --date-max "'+ DateMax +'" '
                       '--variable VHM0  --variable VMDR --variable VTPK --variable crs --variable forecast_period '
                       '--out-dir '+ str(WavePath) +' --out-name "'+ str(WaveOutFile) +'" --user "'+ User +'" --pwd "'+ Pwd +'"')
        os.system(motuCommand)
        
        return WaveOutFile



def SampleWaves(settings, TransectInterGDF, WaveFilePath):
    """
    Function to extract wave information from Copernicus NWS data
    
    FM, Oct 2021 (updated Aug 2023)
    """
    
    print('Extracting wave data to transects ...')
    # open the raster dataset to work on
    with netCDF4.Dataset(WaveFilePath) as WaveData:
    
        # spatial coords returned as arrays of lat and long representing boundaries of raster axis
        # can be rectangular, resulting in differently sized arrays, so transforming as two coordinate arrays doesn't work
        WaveX  = WaveData.variables['longitude'][:]
        WaveY  = WaveData.variables['latitude'][:]

        SigWaveHeight = WaveData.variables['VHM0'][:,:,:]  # Spectral significant wave height (Hs)
        MeanWaveDir = WaveData.variables['VMDR'][:,:,:] # Mean wave direction from (Dir)
        PeakWavePer = WaveData.variables['VTPK'][:,:,:] # Wave period at spectral peak (Tp)
        WaveSeconds = WaveData.variables['time'][:]
        
        WaveTime = []
        for i in range(0,len(WaveSeconds)):
            WaveTime.append(datetime.strptime(datetime.fromtimestamp(WaveSeconds.astype(int)[i]).strftime('%Y-%m-%d %H:%M:%S'),'%Y-%m-%d %H:%M:%S'))
        
        # Calculate time step used for interpolating data between
        TimeStep = (WaveTime[1]-WaveTime[0]).total_seconds()/(60*60)
        
        WaveHs = []
        WaveDir = []
        WaveTp = []
        NormWaveHs = []
        NormWaveDir = []
        NormWaveTp = []
        StDevWaveHs = []
        StDevWaveDir = []
        StDevWaveTp = []
        
        def find(item, lst):
            start = 0
            start = lst.index(item, start)
            return start

        # loop through transects and sample
        for Tr in range(len(TransectInterGDF)):
            print('\r %0.3f %% transects processed' % ( (Tr/len(TransectInterGDF))*100 ), end='')

            InterPnts = TransectInterGDF['interpnt'].iloc[Tr] # midpoints of each transect
            
            if InterPnts == []: # if transect intersect is empty i.e. no veg lines intersected
                TrWaveHs, TrWaveDir, TrWaveTp, TrNormWaveHs, TrNormWaveDir,TrNormWaveTp, TrStDevWaveHs, TrStDevWaveDir, TrStDevWaveTp = (np.nan for i in range(9))
            
            else:
                # get index of closest matching grid square of wave data
                IDLat = (np.abs(WaveY - InterPnts[0].y)).argmin() 
                IDLong = (np.abs(WaveX - InterPnts[0].x)).argmin()
                        
                # per-transect wave data
                TrWaveHs = []
                TrWaveDir = []
                TrWaveTp = []
                TrNormWaveHs = []
                TrNormWaveDir = []
                TrNormWaveTp = []
                TrStDevWaveHs = []
                TrStDevWaveDir = []
                TrStDevWaveTp = []
                
                for i in range(len(TransectInterGDF['dates'].iloc[Tr])): # for each date on each Transect
                    DateTimeSat = datetime.strptime(TransectInterGDF['dates'].iloc[Tr][i] + ' ' + TransectInterGDF['times'].iloc[Tr][i], '%Y-%m-%d %H:%M:%S.%f')
    
                    # Interpolate wave data using number of minutes through the hour the satellite image was captured
                    for WaveProp, WaveSat in zip([SigWaveHeight[:,IDLat,IDLong], MeanWaveDir[:,IDLat,IDLong], PeakWavePer[:,IDLat,IDLong]], 
                                                 [TrWaveHs, TrWaveDir, TrWaveTp]):
                        # if sat image date falls outside wave data window, assign nan
                        if WaveTime[-1] < DateTimeSat:
                            WaveSat.append(np.nan)
                        else:
                            # find preceding and following hourly tide levels and times
                            Time_1 = WaveTime[find(min(item for item in WaveTime if item > DateTimeSat-timedelta(hours=TimeStep)), WaveTime)]                        
                            Wave_1 = WaveProp[find(min(item for item in WaveTime if item > DateTimeSat-timedelta(hours=TimeStep)), WaveTime)]
                            
                            Time_2 = WaveTime[find(min(item for item in WaveTime if item > DateTimeSat), WaveTime)]
                            Wave_2 = WaveProp[find(min(item for item in WaveTime if item > DateTimeSat), WaveTime)]
                            
                            # Find time difference of actual satellite timestamp (next wave timestamp minus sat timestamp)
                            TimeDiff = Time_2 - DateTimeSat
                            # Get proportion of time back from the next 3-hour timestep
                            TimeProp = TimeDiff / timedelta(hours=TimeStep)
                            
                            # Get proportional difference between the two tidal stages
                            WaveDiff = (Wave_2 - Wave_1)
                            WaveSat.append(Wave_2 - (WaveDiff * TimeProp))
    
                    for WaveProp, WaveSat, WaveType in zip([SigWaveHeight[:,IDLat,IDLong], MeanWaveDir[:,IDLat,IDLong], PeakWavePer[:,IDLat,IDLong]], 
                                                       [TrNormWaveHs, TrNormWaveDir, TrNormWaveTp], ['Hs','Dir','Tp']):
                        # if sat image date falls outside wave data window, assign nan
                        if WaveTime[-1] < DateTimeSat:
                            WaveSat.append(np.nan)
                        else:
                            # Smooth over previous 3 month time period and get mean from this range
                            if Time_1-timedelta(days=90) in WaveTime:
                                Prev3Month = WaveTime.index(Time_1-timedelta(days=90))
                             # if timestep doesn't exist for exactly 3 months back, minus an hour
                            elif Time_1-timedelta(days=90,hours=1) in WaveTime:
                                Prev3Month = WaveTime.index(Time_1-timedelta(days=90,hours=1))
                             # if timestep doesn't exist for exactly 3 months back, add an hour
                            elif Time_1-timedelta(days=90,hours=-1) in WaveTime:
                                Prev3Month = WaveTime.index(Time_1-timedelta(days=90,hours=-1))
                            
                            if WaveType == 'Dir':
                                # if dealing with wave dir, use circular mean (to avoid problems with dirs around N i.e. 0deg)
                                SmoothWaveProp = Toolbox.CircMean(WaveProp[Prev3Month:WaveTime.index(Time_1)])
                            else:
                                SmoothWaveProp = np.mean(WaveProp[Prev3Month:WaveTime.index(Time_1)])
                            WaveSat.append(SmoothWaveProp)
                        
                    for WaveProp, WaveSat, WaveType in zip([SigWaveHeight[:,IDLat,IDLong], MeanWaveDir[:,IDLat,IDLong], PeakWavePer[:,IDLat,IDLong]], 
                                                       [TrStDevWaveHs, TrStDevWaveDir, TrStDevWaveTp], ['Hs','Dir', 'Tp']):
                        # if sat image date falls outside wave data window (only updated every 3 months or so), assign nan
                        if WaveTime[-1] < DateTimeSat:
                            WaveSat.append(np.nan)
                        else:
                            # Smooth over previous 3 month time period and get stdev from this range
                            if WaveType == 'Dir':
                                # if dealing with wave dir, use circular std (to avoid problems with dirs around N i.e. 0deg)
                                StDevWaveProp = Toolbox.CircStd(WaveProp[Prev3Month:WaveTime.index(Time_1)])
                            else:
                                StDevWaveProp = np.std(WaveProp[Prev3Month:WaveTime.index(Time_1)])
                            WaveSat.append(StDevWaveProp)
    
            # append per-transect lists
            WaveHs.append(TrWaveHs)
            WaveDir.append(TrWaveDir)
            WaveTp.append(TrWaveTp)
            NormWaveHs.append(TrNormWaveHs)
            NormWaveDir.append(TrNormWaveDir)
            NormWaveTp.append(TrNormWaveTp)
            StDevWaveHs.append(TrStDevWaveHs)
            StDevWaveDir.append(TrStDevWaveDir)
            StDevWaveTp.append(TrStDevWaveTp)

    return WaveHs, WaveDir, WaveTp, NormWaveHs, NormWaveDir, NormWaveTp, StDevWaveHs, StDevWaveDir, StDevWaveTp


def WaveClimate(TransectInterGDF):
    """
    Calculate indicators of wave climate per transect, following equations of
    Ashton & Murray (2006). 
    - Diffusivity (mu) varies with wave angle and represents the wave climate 
      that leads to either shoreline smoothing (+ve diffusivity, stability) or
      or growth of shoreline perturbations (-ve diffusivity, instability)
    - Instability index (Gamma) represents wave angle with respect to shoreline
      orientation, with 1 = low-angle climate and -1 = high-angle climate
      
    FM March 2024

    Parameters
    ----------
    TransectInterGDF : GeoDataFrame
        GeoDataFrame holding coastal info per cross-shore transect.

    Returns
    -------
    WaveDiffusivity : float
        Wave climate indicating perturbation growth or smoothing.
    WaveInstability : float
        Dimensionless measure of stability in offshore wave vs shore angles.

    """
    
    # for each transect in run
    for Tr in range(len(TransectInterGDF)):
        # Get angle of shore from perpendicular transect angle
        # water on right hand side (coords[0] = onshore, coords[1] = offshore)
        x_on = list(TransectInterGDF.iloc[Tr]['geometry'].coords)[0][0]
        y_on = list(TransectInterGDF.iloc[Tr]['geometry'].coords)[0][1]
        x_off = list(TransectInterGDF.iloc[Tr]['geometry'].coords)[1][0]
        y_off = list(TransectInterGDF.iloc[Tr]['geometry'].coords)[1][1]

        ShoreAngle = 90 - np.rad2deg(math.atan2(y_off - y_on, x_off - x_on))
        
        # Initialise per-wave diffusivity
        Mu = []
        # for each wave data point
        for i in range(len(TransectInterGDF.iloc[Tr]['WaveDir'])):
            Alpha = TransectInterGDF.iloc[Tr]['WaveDir'][i] - ShoreAngle
        
        Mu.append((K2/D) * T**(1/5) * H0**(12/5) * (math.cos(Alpha)**(1/5) * ((6/5) * math.sin(Alpha)**2 - math.cos(Alpha)**2)))
    
    # Net diffusivity (Mu_net)
    WaveDiffusivity = np.sum(Mu * dt) / np.sum(dt)
    
    # Dimensionless instability index (Gamma)
    WaveInstability = np.sum(Mu * dt) / np.sum(abs(Mu) * dt)
    
    return WaveDiffusivity, WaveInstability



def TransformWaves(TransectInterGDF, Hs, Dir, Tp):
    """
    IN DEVELOPMENT
    Airy/linear wave theory transformations for offshore to nearshore wave conditions,
    based on shoaling, refraction, and breaking effects.
    FM Jan 2024

    Parameters
    ----------
    TransectInterGDF : GeoDataFrame
        GeoDataFrame holding coastal info per cross-shore transect.
    Hs : TYPE
        DESCRIPTION.
    Dir : TYPE
        DESCRIPTION.
    Tp : TYPE
        DESCRIPTION.

    Returns
    -------
    None.

    """
    for Tr in range(len(TransectInterGDF)): # for each transect
        Hs_mask = Hs.copy()
        Dir_mask = Dir.copy()
        Tp_mask = Tp.copy()
        
        # Mask data for onshore waves only (waves less than shoreline orientation)
        # need to preserve the matrix size so that theta_0 can be calculated
        # previous method of taking a mean doesn't work on curved west-facing bay
        # since half is 270-360 and half is 0-180 giving a weird mean
        # new way: straight line from edges of hard headland to get mean = 45
        
        
        # create new wave direction with index of masked values
        # 90 - atan2(y2-y1, x2-x1)
        # shoreAngle = 90 - np.rad2deg(math.atan2(S.Y(end-1)-S.Y(1), S.X(end-1)-S.X(1)));
        dX = TransectInterGDF['geometry'].iloc[Tr].bounds[2] - TransectInterGDF['geometry'].iloc[Tr].bounds[0]
        dY = TransectInterGDF['geometry'].iloc[Tr].bounds[3] - TransectInterGDF['geometry'].iloc[Tr].bounds[1]
        shoreAngle = 90 - np.rad2deg(math.atan2(dY, dX))
        
        for W in range(len(Dir)): # for each wave condition recorded on each transect intersection
            if Dir[W] > shoreAngle and Dir[W] < shoreAngle+180:
                    Dir_mask[W] = np.nan
    
        #Dir_mask(Dir > shoreAngle && Dir < shoreAngle+180) = NaN; 
        #Dir_mask(Dir > shoreAngle+180) = NaN;
        mask = np.isnan(Dir_mask)
        Tp_mask[mask] = np.nan
        Hs_mask[mask] = 0   # using NaN mask caused issues with breaking condition loop; changed to Hs=0
            
        # Preallocation to save memory
        # waves = struct('ID', np.nan ,'t', np.nan ,'Dir', np.nan ,'Hs', np.nan ,'Tp', np.nan );
        waves = {'ID':np.nan ,'t':np.nan ,'Dir':np.nan ,'Hs':np.nan ,'Tp':np.nan}
        
        ## Shadow zones
        # From the intersection of offshore wave directions with two points 
        # along the shoreline.    
        
        g  = 9.81   # gravity m^s^2
        rho = 1025  # water density
    
        Nloop = 0    # breaking wave loop counter updates
        
        # Re-initialise shadow zone logic table for each transect
        for W in range(len(Hs)):    # for each wave condition recorded on each transect intersection

            Hs_maskSh = Hs_mask[W]
            Tp_maskSh = Tp_mask[W]
            Dir_maskSh = Dir_mask[W]
            
            # If transect sits in shadow of other transect/coast at a particular wave angle
            # TO DO: shadowing routine
            shadow = 0
            if shadow==1:
                Hs_maskSh = 0
                Tp_maskSh = np.nan
                Dir_maskSh = np.nan
            
            H_0 = Hs_maskSh
            C_0 = np.divide( (g*Tp_maskSh) , (2*np.pi) )   # Deepwater wave speed (m/s)
            L_0 = np.multiply( C_0 , Tp_maskSh )        # Deepwater wavelength (m) set by speed and period
            h = 3 * H_0   # water depth at wave base for later calcs of Hs
            
            # Define offshore wave condition based on shadow zone masking
            # Calculate wave energy
            En = (1/8) * rho * g * np.dot(H_0, 2)
            
            BREAK_WAV = 0  # flag for wave breaking  
            
            while BREAK_WAV == 0:
                
                # Calculate wave conditions in shallow water depth
                L = np.multiply( L_0 , (np.tanh( ( np.multiply((np.square(np.divide((2*np.pi),Tp_maskSh))) , (h/g)) )**(3/4) )) )**(2/3)    # wavelength; tanh(x)=1 when -2pi<x<2pi
                C = np.multiply( C_0 , np.tanh(np.multiply((2*np.pi*h) , L)) )  # shallow wave speed
                k = np.divide((2*np.pi),L)    # wave number (1/m)
                
                # Calculate shoaling coefficient
                n = ( np.divide( np.multiply((2*h),k) , (np.sinh(np.multiply((2*h),k))) ) + 1 ) / 2    # shoaling factor
                Ks = np.sqrt( np.divide(C_0 , np.multiply(np.multiply(n,C),2)) )   # shoaling coefficient
                
                # Calculate refraction coefficient
                if shoreAngle > 0 and shoreAngle < 90:
                    # theta_0 is wave dir wrt shore angle
                    Theta_0 = shoreAngle + 270 - Dir_maskSh 
                else:
                    Theta_0 = shoreAngle - 90 - Dir_maskSh
                
                Theta = np.rad2deg( math.asin( np.multiply(np.divide(C,C_0) , math.sin(np.deg2rad(Theta_0)) )) )   # update theta
                Kr = math.sqrt(abs(math.cos(np.deg2rad(Theta_0))/math.cos(np.deg2rad(Theta))))
                # update conditions using refracted shoaled waves
                Hs_near = H_0*Ks*Kr
                if shoreAngle > 0 and shoreAngle < 90:
                    Dir_near = shoreAngle+270-Theta    # recalculating direction using theta
                else:
                    Dir_near = shoreAngle-90-Theta
                    if Dir_near < 0:
                        Dir_near=360+Dir_near   # need to check this! was *-1, but this swings -ve values back W from N
                    
                
                Tp_near = Tp_maskSh[W,1] # offshore period
                
                # Test if the wave meets breaking conditions
                if Hs_near > h*0.78:
                    BREAK_WAV = 1
                    Hs_break = Hs_near # to record per timeseries AND transect
                    Dir_break = Dir_near #  offshore cond.
                    Tp_break = Tp_maskSh[W,1] 
                    Nloop = Nloop + 1    # breaking wave loop counter updates
                
                
                # Reduce water depth by -10cm each loop
                h = h-0.10
                
                # Catch negative water depths (assume 0 transport and set
                # wave height and transport angle to 0)
                if h<0:
                    Hs_break[W,Tr] = 0
                    if shoreAngle > 0 and shoreAngle < 90: # for shoreline angles <90 (perpendicular transformation of -90 leads to -ve values) 
                        # need conditionals for Dir orientations too
                        if Dir_near > shoreAngle+270:    # 0-90 + 270 = for waves 270-360
                            Dir_break[W,Tr] = shoreAngle # transport rate = 0 when alpha = +90
                        elif np.isnan(Dir_near):  # to catch offshore (NaN) wave directions
                            Dir_break[W,Tr] = np.nan
                        else:
                            Dir_break[W,Tr] = shoreAngle+180 # transport rate = 0 when alpha = -90
                        
                    else: # for shoreline angles 90-360
                        # need conditionals for Dir orientations too
                        if Dir_near > shoreAngle-90:     # 90-360 - 90 = for waves 0-270
                            Dir_break[W,Tr] = shoreAngle # transport rate = 0 when alpha = +90
                        elif np.isnan(Dir_near):  # to catch offshore (NaN) wave directions
                            Dir_break[W,Tr] = np.nan
                        else:    # for Dir_near less than alpha_shore-90                      
                            Dir_break[W,Tr] = shoreAngle-180 # transport rate = 0 when alpha = -90
                            if Dir_break[W,Tr] < 0: #added condition for when alpha_shore-90 becomes negative (alpha<135)
                                Dir_break[W,Tr] = 360 + Dir_break[W,Tr]
 
                    
                    Tp_break[W,Tr] = Tp_maskSh[W,1] # offshore cond.
                    BREAK_WAV = 1 # ignore refraction in this case, wave has already refracted around
                     
                # use loop vars to write transformed wave data to structure
                waves['ID'][Tr] = TransectInterGDF['TransectID'].iloc[Tr]
                waves['t'][Tr][W,1] = str(TransectInterGDF['dates'].iloc[Tr][W]+' '+TransectInterGDF['times'].iloc[Tr][W])
                waves['alpha_shore'] = shoreAngle
                waves['Dir_near'][Tr][W,1] = Dir_near    
                    
            # condition to store both types of waves (near/breaking)
            if BREAK_WAV == 1:
                waves['Dir'][Tr][W,1] = Dir_break[W,Tr]
                waves['Hs'][Tr][W,1] = Hs_break[W,Tr]
                waves['Tp'][Tr][W,1] = Tp_break[W,Tr]
            else:
                waves['Hs'][Tr][W] = Hs_near
                waves['Tp'][Tr][W,1] = Tp_near
                waves['Dir'][Tr][W,1] = Dir_near
                

        print('number of breaking wave conditions: '+str(Nloop))

