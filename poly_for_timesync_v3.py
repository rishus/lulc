#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
Created on Sat Nov 25 16:53:01 2017

@author: rishu
"""

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Created on Mon Sep 26 08:26:14 2016

@author: rishu
"""

import numpy as np
import bfast  as bf
import ewmacd as ew
import landTrendR  as ltr
# for remote desktop:
#import matplotlib as mpl
#mpl.use('Agg')
from collections import defaultdict
from matplotlib import pylab as plt
import datetime as dt
import matplotlib.ticker as ticker
import matplotlib.dates as mdates

time1 = 2000
time2 = 2012 + 1
eps = 1
if time1 == 2000:
    tickGap = 2
    dist_thresh = 13.0  # because an otherwise good algorithm outcome could have one breakpoint lurking around at far end.
                        # We don't want to lose this result just because of that false alarm.
    min_ew_brks = 0
    max_brks = 3
else:
    tickGap = 4
    dist_thresh = 25.0  # because an otherwise good algorithm outcome could have one breakpoint lurking around at far end.
                        # We don't want to lose this result just because of that false alarm.
    min_ew_brks = 1
    max_brks = 5     # for 13 year time period, 3 breaks would be enough?!
                     # For 25 years, 5 break would be good. 
                     # For 6 years, 2 breaks would be enough.
# parameters for ewmacd
ew_num_harmonics = 2  # was 2 earlier
ew_ns = ew_num_harmonics
ew_nc = ew_num_harmonics
ew_xbarlimit1 = 1.5
ew_xbarlimit2 = 20
ew_lowthreshold = 0
ew_trainingStart = time1
if time1 == 2000:
    ew_trainingEnd= time1 + 2
else:
    ew_trainingEnd= time1 + 3
ew_mu = 0
ew_L = 3.0   # default is 3.0
ew_lam = 0.5   # default is 0.5
ew_persistence = 7  # default is 7
ew_summaryMethod = 'on-the-fly'   #'reduced_wiggles'  # 'annual_mean'  #

# parameters for bfast
bf_h = 0.15
bf_numBrks = 2 #max_brks
bf_numColsProcess = 1
bf_num_harmonics = ew_num_harmonics  #1
bf_pval_thresh = 0.05  #default is 0.05
bf_maxIter = 2
bf_frequency = 23

# parameters for landtrendr
ltr_despike_tol = 0.9  # 1.0, 0.9, 0.75, default is 0.9
ltr_pval = 0.2          # 0.05, 0.1, 0.2, default is 0.2
ltr_mu = 6  #max_brks + 1   #mpnu1     # 4, 5, 6, default is 6
ltr_recovery_threshold = 1.0  # 1, 0.5, 0 25
ltr_nu = 3              # 0, 3
ltr_distwtfactor = 2.0   #i have taken this value from the IDL code
ltr_use_fstat = 0        #0 means 'use p_of_f', '1' is for 'dont use p_of_f'.
                               #So if use_fstat = 0, the code will use p_of_f.

ltr_best_model_proportion = 0.75
colors = ['green', 'sandybrown', 'black']
dashes = [[12, 6, 12, 6], [12, 6, 3, 6], [3, 3, 3, 3]] # 10 points on, 5 off, 100 on, 5 off
#    line_styles = ['--','s--',':']
line_widths = [4, 5, 2]

def data_from_timeSyncCsvFile(path, mat_all_lines, fn_groundTruth, my_pid, time_start, time_end):

    num_lines = len(mat_all_lines)
    this_pixel_info ={'sensor': [], 'pid':  [], 'yr': [],  \
                      'doy': [], 'b3': [], 'b4': [], 'b5': [], \
                      'b6': []}
    num_obs = 0
    for line in range(num_lines):
        mat_vals = mat_all_lines[line].strip().split(',')
        if (int(mat_vals[1]) == my_pid) and (mat_vals[0]!= '' and \
                      mat_vals[1]!= '' and mat_vals[2] != '' and \
                      mat_vals[4]!= '' and mat_vals[5]!='' and \
                      mat_vals[8]!='' and mat_vals[9]!='' and 
                      mat_vals[10]!='' and mat_vals[12]!=''): # and \
#                      int(mat_vals[13])==0):
            #sensor, pid, tsa, plotid, year, doy, band3, band4, band5, band6
                
            this_pixel_info['sensor'].append(int(mat_vals[0][2]))
            this_pixel_info['yr'].append(int(mat_vals[4]))
            this_pixel_info['doy'].append(int(mat_vals[5]))
            try:
                if (int(mat_vals[13]) not in [0, 1]):   # cloud, water etc masking
                    this_pixel_info['b3'].append(-9999)
                    this_pixel_info['b4'].append(-9999)
                    this_pixel_info['b5'].append(-9999)
                    this_pixel_info['b6'].append(-9999)
                else:
                    this_pixel_info['b3'].append(int(mat_vals[8]))
                    this_pixel_info['b4'].append(int(mat_vals[9]))
                    this_pixel_info['b5'].append(int(mat_vals[10]))
                    this_pixel_info['b6'].append(int(mat_vals[12]))
            except:
                    this_pixel_info['b3'].append(-9999)
                    this_pixel_info['b4'].append(-9999)
                    this_pixel_info['b5'].append(-9999)
                    this_pixel_info['b6'].append(-9999)
            num_obs +=1

    tyeardoy_all = np.zeros((num_obs, 2))
    vec_obs_all = []
    tyeardoy_all[:, 0] = this_pixel_info['yr']
    tyeardoy_all[:, 1] = this_pixel_info['doy']
    for i in range(num_obs):
        red = float(this_pixel_info['b3'][i])
        nir = float(this_pixel_info['b4'][i])
        if (abs(nir+red) < np.finfo(float).eps):
            vec_obs_all.append(-9999)
        else:
            ndvi = ((nir-red)/(nir+red))
            if ndvi < 0 or ndvi >1:
                vec_obs_all.append(-9999)
            else:
                vec_obs_all.append(ndvi * 10000)

    # limit returns to the desired time span
    a = [i for i in range(len(vec_obs_all)) \
            if (tyeardoy_all[i, 0] >= time_start) and (tyeardoy_all[i, 0] < time_end)]

    tyeardoy = np.zeros((len(a), 2))
    ctr = 0
    for i in a:
        tyeardoy[ctr, 0] = int(tyeardoy_all[i, 0])
        tyeardoy[ctr, 1] = int(tyeardoy_all[i, 1])
        ctr += 1

    vec_obs = np.asarray([vec_obs_all[i] for i in a])
    # notice that tyeardoy is sent out as an array while vec_obs is sent as a list.
    # well, not any more
    
    # Now get the ground truths. Note that only disturbance pixels are included in the
    # ground truth sheet.
    mat_all_changes = []
    with open(fn_groundTruth, 'r') as f_gt:
        first_line = f_gt.readline()
        for i, line in enumerate(f_gt):
            this_line = line.strip().split(',')
            if int(this_line[0]) == my_pid:
                mat_all_changes.append(line)
            pass

    num_changes = 0
    changes = []
    # Note that if pid is a no-disturbance-ever pixel, then mat_all_changes will be empty anyways.
    # So this loop won't run. 
    # So, basically, the 'else' statement in the loop gets executed only for pids where some lu-cover info is available.
    for line in mat_all_changes:
        mat_gt_vals = line.strip().split(',')
        s_yr = mat_gt_vals[1]
        e_yr = mat_gt_vals[2]
        s_lu = mat_gt_vals[5]
        e_lu = mat_gt_vals[6]
        if ((int(s_yr) >= time_start) and (int(e_yr) <= time_end)):
            num_changes +=1
            change_type = mat_gt_vals[3]
            changes.append([s_yr, e_yr, change_type, s_lu, e_lu])
        else:
            changes.append(['x','x','x', s_lu, e_lu])
    changes = [num_changes] + changes

    return vec_obs, tyeardoy, changes

    
def process_pixel(tyeardoy, vec_obs_original, pixel_info, tickGap, changes, dist_thresh):
# this subroutine is for a fixed set of parameters. It is able to process multiple bands

    time1 = pixel_info[0]
    pid = pixel_info[1]
    num_bands = len(vec_obs_original)  # becuz vec_obs_original is a list
    num_obs = tyeardoy.shape[0]

#    fig, ax = plt.subplots()
#    fig.set_size_inches(8,6)
#    ax.plot()
#    years_all = [int(tyeardoy[i, 0]) for i in range(0, num_obs)]
#    doys_all = [int(tyeardoy[i, 1]) for i in range(0, num_obs)]
#    dates_all = [dt.datetime(year, 1, 1) + dt.timedelta(day - 1) for year,day in zip(years_all,doys_all)]
    for band in range(num_bands):

        # ************* develop the presInd vector and check training data availability ***********************
        presInd = np.where(vec_obs_original[band] > ew_lowthreshold)[0]      # all presentIds.
        tyeardoy_idxs = np.where(np.logical_and(ew_trainingStart<= tyeardoy[:,0], \
                                                tyeardoy[:,0]< ew_trainingEnd))[0] # all indices in the training period.
        common_idx = list(set(tyeardoy_idxs).intersection(presInd))  # presentIds in the training period.
        training_t = tyeardoy[common_idx, 1]    # only doys in the training period.
        #Corner case
        if (len(training_t) < 2 * ew_num_harmonics + 1):    #from ewmacd
           print   pid, ': too little training data'
           return [], [], [], [], 'insuff'

#        brkptsummary is needed in these 1D codes to make 1D plots. But for 2D, it is redundant.
        tmp2, ewma_summary, ew_brks_GI, ew_brkpts, ew_brkptsummary =    \
                                 ew.ewmacd(tyeardoy, vec_obs_original[band], presInd, \
                                 ew_num_harmonics, ew_xbarlimit1, ew_xbarlimit2, \
                                 ew_lowthreshold, ew_trainingStart, ew_trainingEnd, \
                                 ew_mu, ew_L, ew_lam, ew_persistence, \
                                 ew_summaryMethod, ew_ns, ew_nc, 'dummy')

        bf_brks_GI, bf_brkpts, bfast_trendFit, bf_brkptsummary = \
                    bf.bfast(tyeardoy, vec_obs_original[band], presInd, \
                             ew_trainingStart, ew_trainingEnd, ew_lowthreshold, ew_num_harmonics, \
                             bf_frequency, bf_numBrks, bf_num_harmonics, bf_h, bf_numColsProcess, \
                             bf_pval_thresh, bf_maxIter)

        bestModelInd, allmodels_LandTrend, ltr_brks_GI, ltr_brkpts, ltr_trendFit, ltr_brkptsummary = \
                        ltr.landTrend(tyeardoy, vec_obs_original[band], presInd, \
                          ew_trainingStart, ew_trainingEnd, ew_lowthreshold, ew_num_harmonics, \
                          ltr_despike_tol, ltr_mu, ltr_nu, ltr_distwtfactor, \
                          ltr_recovery_threshold, ltr_use_fstat, ltr_best_model_proportion, \
                          ltr_pval)

        ####### compare different algorithm results #########
        # pairwise distance between brkpts
        # Does any algorithm indicate breakpoint during the training period?
        use_ewma = 'yes'
        for brk in bf_brkpts[1:]:
            if brk[0] in range(ew_trainingStart, ew_trainingEnd+1):
                use_ewma = 'no'

#        print 'bf: ', bf_brkpts[1:-1], '\n'
#        print 'ltr: ', ltr_brkpts[1:-1], '\n'
#        print 'ew: ', ew_brkpts[1:-1], '\n'
        bf_brkpts_m = [(i[0] + min(i[1], 365)/365.) for i in bf_brkpts[1:-1]]
#        print 'B = ', bf_brkpts_m
        ltr_brkpts_m = [(i[0] + min(i[1], 365)/365.) for i in ltr_brkpts[1:-1]]
#        print 'L = ', ltr_brkpts_m
        ew_brkpts_m = [(i[0] + min(i[1], 365)/365.) for i in ew_brkpts[1:-1]]
#        print 'E = ', ew_brkpts_m
        dist_BL = dist(bf_brkpts_m, ltr_brkpts_m, 'no')
        dist_LB = dist(ltr_brkpts_m, bf_brkpts_m, 'no')
        if use_ewma == 'yes':
            dist_BE = dist(bf_brkpts_m, ew_brkpts_m,'no')
            dist_EB = dist(ew_brkpts_m, bf_brkpts_m,'no')
            dist_LE = dist(ltr_brkpts_m, ew_brkpts_m, 'no')
            dist_EL = dist(ew_brkpts_m, ltr_brkpts_m, 'no')
        else:
            dist_BE = 1000000
            dist_EB = 1000000
            dist_LE = 1000000
            dist_EL = 1000000
        
        vec_dists = [dist_BE, dist_EB, dist_BL, dist_LB, dist_LE, dist_EL]
        s_ind = vec_dists.index(min(vec_dists))
#        if s_ind in [2, 3] and dist_BL==dist_LB:
#            s_ind = random.sample(set([2,3]), 1)[0]
#        if s_ind in [0, 1] and dist_BE == dist_EB:
#            s_ind = random.sample(set([0,1]), 1)[0]
#        if s_ind in [4, 5] and dist_LE == dist_EL:
#            s_ind = random.sample(set([4,5]), 1)[0]
#        print 'vec_dists = ', vec_dists
#        print 'min housdorff distance: ', vec_dists[s_ind]
        if vec_dists[s_ind] <= dist_thresh:
            if s_ind in [0, 2]:
                polyAlgo_brkpts = bf_brkpts
                winner = 'bf'
            elif s_ind in [1, 5]:
                polyAlgo_brkpts = ew_brkpts
                winner = 'ew'
            else:  # s_ind in [3, 4]
                polyAlgo_brkpts = ltr_brkpts
                winner = 'ltr'
        else:
            # if no agreement, then declare it stable
            polyAlgo_brkpts = [0, num_obs-1]
            winner = 'none'
        
        with open("polyalgo_distances.csv", "a") as fh:
            fh.write(str(pid) + ', ' + str(vec_dists[s_ind]) + ', ' +  str(dist_BE) + ',   ' + str(dist_EB) +  ',   '  +  \
                                                           str(dist_BL) + ',   ' + str(dist_LB) +  ',   '   + \
                                                           str(dist_LE) + ',   ' + str(dist_EL) +  ',   '  + \
                                                           str(s_ind) + ',    ' + winner + '\n')
        fh.close()
        
        ####### plot outputs and input #########
        if len(presInd) == 0:
            print 'presInd = 0 in processPixel'
            return

        bf_trendFit_scaled = [float(bfast_trendFit[i])/float(10000) for i in range(num_obs)]
        bf_trendFit_scaled = [float(bf_brkptsummary[i])/float(10000) for i in range(num_obs)]
#        ltr_trendFit_scaled = [float(ltr_trendFit[i])/float(10000) for i in range(num_obs)]
        ltr_trendFit_scaled = [float(ltr_brkptsummary[i])/10.0 for i in range(num_obs)]
#        ew_flags_scaled = [float(ewma_summary[i])/float(10) for i in range(num_obs)]
        ew_flags_scaled = [float(ew_brkptsummary[i])/float(10) for i in range(num_obs)]
        
        plot_trajectories(pid, time1, tyeardoy, num_obs, vec_obs_original[band], presInd, \
                      tickGap, ew_flags_scaled, ltr_trendFit_scaled, bf_trendFit_scaled, \
                      winner, changes, colors, dashes, line_widths)

    return bf_brkpts[1:-1], ew_brkpts[1:-1], ltr_brkpts[1:-1], polyAlgo_brkpts[1:-1], winner


def dist(A, B, toprint):

    lA = len(A)
    lB = len(B)
    if lA == 0 and lB == 0:
        return 0
        
    if lA == 0 and lB != 0:
        return 1000000
    if lB == 0 and lA != 0:
        return 1000000

    dists_AB = np.zeros((lA, lB))
    daB = np.zeros( (lA,) )
    for i in range(lA):
        # get d(a, B)
        for j in range(lB):
            dists_AB[i, j] = abs(A[i]-B[j])
            
        daB[i] = min(dists_AB[i,:])
    if toprint == 'bl':
        print 'BFAST, LTR:'
    if toprint == 'lb':
        print 'LTR, BFAST'
    if toprint in ['bl','lb']:
        print 'A: ', A
        print 'B: ', B
        for i in range(lA):
            print dists_AB[i,:]
        
        print 'daB = ', daB

    dAB = max(daB)
    if toprint in ['bl','lb']:
        print 'dAB = ', dAB
    
    return dAB


def plot_trajectories(pid, time1, tyeardoy, num_obs, vec_obs_original, presInd, \
                      tickGap, ew_flags_scaled, ltr_trend_scaled1, bf_trendFit_scaled, \
                      winner, changes, colors, dashes, line_widths):

    fig, ax = plt.subplots()
    fig.set_size_inches(8,6)
    ax.plot()
    years_all = [int(tyeardoy[i, 0]) for i in range(0, num_obs)]
    doys_all = [int(tyeardoy[i, 1]) for i in range(0, num_obs)]
    dates_all = [dt.datetime(year, 1, 1) + dt.timedelta(day - 1) for year,day in zip(years_all,doys_all)]
    vec_obs_pres = [vec_obs_original[i] for i in presInd]
    Sfinal = len(presInd)
    years = [int(tyeardoy[i, 0]) for i in presInd]
    doys = [int(tyeardoy[i, 1]) for i in presInd]
    dates = [dt.datetime(year, 1, 1) + dt.timedelta(day - 1) for year,day in zip(years,doys)]
    datemin = dt.date(min(dates).year, 1, 1)
    datemax = dt.date(max(dates).year + 1, 1, 1)
    year_tics = sorted(set([dt.date(d.year,1, 1) for d in dates]))
    ticklabels = ['']*len(year_tics)
    ticklabels[::tickGap] = [item.strftime('%Y') for item in year_tics[::tickGap]]    # Every 5th ticklable shows the month and day

    vec_obs_pres_plot = [float(vec_obs_pres[i])/float(10000) for i in range(Sfinal)]
    line, = ax.plot(dates, vec_obs_pres_plot, '--', color=colors[0], \
            linewidth=2, markersize=6 , label='NDVI')  #+str(band))
    line.set_dashes(dashes[0])
    ax.plot(dates_all, ltr_trend_scaled1, '-', color=colors[0], linewidth=line_widths[0], label='LandTrendR')
    ax.plot(dates_all, bf_trendFit_scaled, '-', color=colors[1], linewidth=line_widths[0], label='BFAST')
    ax.plot(dates_all, ew_flags_scaled, '--', color=colors[2], linewidth=3, label='EWMACD/10')

    legend = ax.legend(loc='best', fontsize=14, shadow=True)
    frame = legend.get_frame()
    legend.get_frame().set_alpha(0.5)
    frame.set_facecolor('white')
    years = mdates.YearLocator(tickGap, month=7, day=4)   # Tick every 5 years on Jan 1st #July 4th
    yearsFmt = mdates.DateFormatter('%Y')
    ax.xaxis.set_major_locator(years)
    ax.xaxis.set_major_formatter(yearsFmt)
    ax.set_xlim(datemin, datemax)
#        ax.set_ylim(-0.1, 1.0)  #(min(ewmacd_flags_scaled)-0.05, 1.0)
    ax.xaxis.set_major_formatter(ticker.FixedFormatter(ticklabels[::tickGap]))
    ax.format_xdata = mdates.DateFormatter('%Y-%m-%d')
    title_str = []
    xlabel_str = []
#        changes = [s_yr, e_yr, change_type, s_lu, e_lu]
    for element in changes[1:]:
        tmp = ','.join([element[0], element[1], element[2][0:3]])
        tmp_lu_changes = '-->.'.join([element[3][0:3], element[4][0:3]])
        title_str.append(tmp)
        xlabel_str.append(tmp_lu_changes)
    plt.title(title_str)
    xlabel_str.append('  ' + winner)
    plt.xlabel(xlabel_str)
    plt.rcParams.update({'font.size': 22})

    fig_path = '/home/rishu/research/thesis/myCodes/thePolyalgorithm/timeSyncOutputs/harvest_editedData/'
#    fig_path = '/home/rishu/research/thesis/presentations/rs_journal/submission1/'
#    fig_path = '/home/rishu/research/thesis/presentations/thesis/presentation/'
    
    fig_name = 'all_' + str(time1) + "to12_" + str(pid) + '_nobias'+  '.png'
#    fig_name =  'ltr_' + str(time1) + "to12_" + str(pid) + \
#                      '_despike_tol' + str(ltr_despike_tol) + \
#                     ',pval' + str(ltr_pval) + ',mu' + str(ltr_mu) + \
#                      ',nu' + str(ltr_nu) + ',trec' + str(ltr_recovery_threshold) + '.eps'
#    fig_name =  'ew_' + str(time1) + "to12_" + str(pid) +  \
#                     ',lam' + str(ew_lam) + ',L' + str(ew_L) + \
#                     ',pers' + str(ew_persistence) + '.eps'
#    fig_name =  'bf_' + str(time1) + "to12_" + str(pid) +  '.eps'  #\
#                     '_h' + str(bf_h) + ',brks' + str(bf_numBrks) + \
#                     ',pval' + str(bf_pval_thresh) + ',numHarm' + str(bf_num_harmonics) + '.eps'
    full_fig_name = fig_path  + fig_name
    fig.savefig(full_fig_name, bbox_inches='tight', format='png')
    
    return


def process_timesync_pixels(path = "/home/rishu/research/thesis/myCodes/thePolyalgorithm/"):

    fn_timeSync_pids = path + "timeSync_pids_harvest.csv"   # "conus_allStable_pids.csv"   #
    fn_timeSync_ts = path + 'conus_spectrals.csv'
    fn_timeSync_disturbance = path + "timeSync_pids_anyChange00to12.csv"    #'ts_disturbance_segments.csv'  #

    pixels_list = []
    with open(fn_timeSync_pids, 'r') as f:
        for i, line in enumerate(f):
            line_vals = line.strip().split(',')
            pixel = int(line_vals[0])
            if pixel not in pixels_list:
                pixels_list.append(pixel)
            pass

#    pixels_list = [13032007, 17036006, 21040009, 40037036, 43031037, 26041029, 26036035, 17036006, 15034028]
#    pixels_list =  [16041003] #[14034031, 20033023, 15034028, 26041029] # ewmacd
#    pixels_list = [11031001]  #[15035029, 26041011, 14033005, 13032007]  # ltr
#    pixels_list = [16040026, 16037001, 16037027, 18031030]    # bf [16035005]  #
#    pixels_list = [14036011, 16035005, \
#                   43031037, 26036035, 18031030, 16040026, \
#                   16037001, 12030015, 16035005, 16037027, \
#                   20037039, 26041011, 15035029, 14033005, \
#                   11031001, 16041018, 13032007, 14034031, \
#                   15034028, 16041003, 26041029, 15037026, 15035003,
#                   23036020, 16041003, 23036016, 15034028]
        # [11031001, 12030015, 13032007, 14031035]:  # urbanization
#                  17036006, 13032007, 26041029, 42034039, 43031037, \
#                  ]:  #15037026, 16041003,
#        [18031030, 16040026, 16037001, 12030015, \
#                  16035005, 16037027, 20037039, \
#                  26041011, 15035029, 14033005, 11031001, \
#                  16041018, 13032007,\
#                  14034031, 15034028, 16037001, 14033005, 16041003, \
#                  26041029, 15037026, 20037039]:
        # bf: [18031030, 16040026, 16037001, 12030015, 16035005, 16037027, 20037039]
        # ltr: [26041011, 15035029, 14033005, 11031001, 13032007, 16041018]
        # ewma: [14034031, 20033023, 15034028, 16037001, 14033005, 16041003]
        # ewma candidates: [  11031001, 14033005, 14034031, 14036011, 14036003,  \
#                    15037026, 15034028, 16037001, 16041003, \
#                    26041029]
    mat_all_timeseries = defaultdict(list)
    with open(fn_timeSync_ts, 'r') as f:
        first_line = f.readline()
        for i, line in enumerate(f):
            this_line = line.strip().split(',')
            if int(this_line[1]) in pixels_list:
                mat_all_timeseries[int(this_line[1])].append(line)
            pass

#    with open("polyalgo_distances.csv", "w") as fh:
#        fh.write('pid    BE    EB    BL    LB    LE    EL    winner' + '\n')
#    fh.close()

    bfast_false_negatives = 0
    bfast_true_positives = 0
    ewma_false_negatives = 0
    ewma_true_positives = 0
    ltr_false_negatives = 0
    ltr_true_positives = 0
    polyAlgo_false_negatives = 0
    polyAlgo_true_positives = 0
    num_true_brks = 0
    ew = 0
    bf = 0
    ltr = 0
    nun = 0
    insuff = 0
    num_change_pixels = 0
    change_bf_says_change = 0
    change_bf_says_stable = 0
    change_ew_says_change = 0
    change_ew_says_stable = 0
    change_ltr_says_change = 0
    change_ltr_says_stable = 0
    change_poly_says_change = 0
    change_poly_says_stable = 0
    num_stable_pixels = 0
    stable_bf_says_stable = 0
    stable_bf_says_change = 0
    stable_ew_says_stable = 0
    stable_ew_says_change = 0
    stable_ltr_says_stable = 0
    stable_ltr_says_change = 0
    stable_poly_says_stable = 0
    stable_poly_says_change = 0
    problem_pixels = []
    print 'total pixels =', len(pixels_list)
    fn_pids = []
    for pixel in pixels_list:  #40027038, 38029024]:  #pixels_list:

        my_pid = pixel  #int(pixel[0:-1])
#        print my_pid
        #######################################################################
        vec_obs_original_ndvi, tyeardoy, changes = data_from_timeSyncCsvFile( \
                            path, mat_all_timeseries[my_pid], fn_timeSync_disturbance, my_pid, time1, time2)
        
        if (len(tyeardoy) != len(vec_obs_original_ndvi)) or (len(tyeardoy) == 0):
            problem_pixels.append(my_pid)
            continue

        vec_obs_original = [] 
        vec_obs_original.append(vec_obs_original_ndvi)
        # vec_obs_original is a list of arrays. Each array cors to 1 band.
        pixel_info = [time1, my_pid]

#        try:
            bfast_brkpts, ewma_brkpts, ltr_brkpts, polyAlgo_brkpts, winner = \
                process_pixel(tyeardoy, vec_obs_original, pixel_info, tickGap, changes, dist_thresh)
#        except:
#            print 'problem pixel', my_pid
#            continue

#       ########## counting selections #########
        if winner == 'ew':
            ew += 1
        if winner == 'bf':
            bf += 1
        if winner == 'ltr':
            ltr += 1
        if winner == 'none':
            nun += 1
        if winner == 'insuff':
            insuff += 1

#        ######### determine the accuracy ########
        ground_truth_bps = []
#        changes = [s_yr, e_yr, change_type, s_lu, e_lu]
        for element in changes[1:]:
            try:
                ct = element[2]
                start_yr = int(element[0])
                end_yr = int(element[1])
#                if ct != 'x':
                if ct == 'Harvest':  # we are not going to do any case of Sit. 
                                  # So, even if an Sit follows a Harvest, it
                                  # will not be included in ground_truth_bps
                                  # This will prevent overcounting Harvest+Sit events.
                    ground_truth_bps.append([start_yr, end_yr])
                    num_true_brks += 1
            except:   # why would be get an exception here? Well ... when it meets the 'x's we have filled.
                num_true_brks += 0 # basically do nothing

#       ########## counting change vs no change #########
        if changes[0] > 0:
            # timesync says there was a change
#            print my_pid, changes
            num_change_pixels += 1
            # does bfast say so?
            if len(bfast_brkpts) > 0:
                # bf also says there was a change. So, success
                change_bf_says_change += 1
            else:
                change_bf_says_stable += 1
            
            if len(ewma_brkpts) > 0:
                change_ew_says_change += 1
            else:
                change_ew_says_stable += 1
                
            if len(ltr_brkpts) > 0:
                change_ltr_says_change += 1
            else:
                change_ltr_says_stable += 1
                
            if len(polyAlgo_brkpts) > 0:
                change_poly_says_change += 1
            else:
                change_poly_says_stable += 1
                
        if changes[0] == 0:
            # timesync says pixel was stable
            # does bfast say so
            num_stable_pixels +=1
            if len(bfast_brkpts) == 0:
                # bf says pixel was stable
                stable_bf_says_stable += 1
            else:
                stable_bf_says_change += 1
                
            if len(ewma_brkpts) == 0:
                stable_ew_says_stable += 1
            else:
                stable_ew_says_change += 1
                
            if len(ltr_brkpts) == 0:
                stable_ltr_says_stable += 1
            else:
                stable_ltr_says_change += 1
            
            if len(polyAlgo_brkpts) == 0:
                stable_poly_says_stable += 1
            else:
                stable_poly_says_change += 1

       ############## accuracy counting ####################
       
        bfast_predictions = set()
        for bp in bfast_brkpts:
            bfast_predictions.add(bp[0])
        # do the breaks we found agree with timesync data?
        break_number_covered = 0
        for bf_element in bfast_brkpts:
            for gth_element in ground_truth_bps[break_number_covered:]:
                if bf_element[0] in range(gth_element[0], gth_element[1]+1):
                    bfast_true_positives += 1
                    break_number_covered += 1  # this is to prevent overcounting.
                                               # Eg., there may be multiple alarms
                                               # for just one event. Especially, with ltr.
                    break
        # did we miss a break suggested in timesync data?
        for gth_element in ground_truth_bps:
            found = False
            for j in range(gth_element[0], gth_element[1]+1):
                if j in bfast_predictions:
                    # bfast did pick this up. So does not contribute to a miss.
                    found = True
                    bfast_predictions.discard(j)
                    break
            if found == False:
                bfast_false_negatives += 1

        ewma_predictions = set()
        for bp in ewma_brkpts:
            ewma_predictions.add(bp[0])
        # do the breaks we found agree with timesync data?
        break_number_covered = 0
        for ew_element in ewma_brkpts:
            for gth_element in ground_truth_bps[break_number_covered:]:
                if ew_element[0] in range(gth_element[0], gth_element[1]+1):
                    ewma_true_positives += 1
                    break_number_covered += 1
                    break
        # did we miss a break suggested in timesync data?
        for gth_element in ground_truth_bps:
            found = False
            for j in range(gth_element[0], gth_element[1]+1):
                if j in ewma_predictions:
                    found = True
                    ewma_predictions.discard(j)
                    break
            if found == False:
                ewma_false_negatives += 1
        
        ltr_predictions = set()
        for bp in ltr_brkpts:
            ltr_predictions.add(bp[0])
        
        # do the breaks we found agree with timesync data?
        break_number_covered = 0
        for ltr_element in ltr_brkpts:
            for gth_element in ground_truth_bps[break_number_covered:]:
                if ltr_element[0] in range(gth_element[0], gth_element[1]+1):
                    ltr_true_positives += 1
                    break_number_covered += 1
                    break
        # did we miss a break suggested in timesync data?
        for gth_element in ground_truth_bps:
            found = False
            for j in range(gth_element[0], gth_element[1]+1):
                if j in ltr_predictions:
                    found = True
                    ltr_predictions.discard(j)  # to prevent same flag for two diferent
                                                # events, especially, when events are 
                                                # back to back.
                    break
            if found == False:
                ltr_false_negatives += 1

        polyAlgo_predictions = set()
        for bp in polyAlgo_brkpts:
            polyAlgo_predictions.add(bp[0])

        # do the breaks we found agree with timesync data?
        break_number_covered = 0
        for poly_element in polyAlgo_brkpts:
            for gth_element in ground_truth_bps[break_number_covered:]:
                if poly_element[0] in range(gth_element[0], gth_element[1]+1):
                    polyAlgo_true_positives += 1
                    break_number_covered += 1
                    break
        # did we miss a break suggested in timesync data?
        for gth_element in ground_truth_bps:
            found = False
            for j in range(gth_element[0], gth_element[1]+1):
                if j in polyAlgo_predictions:
                    found = True
                    polyAlgo_predictions.discard(j)
                    break
            if found == False:
                polyAlgo_false_negatives += 1
                fn_pids.append(my_pid)


#        bf_total_num_sigs += len(bfast_brkpts)
#        bfast_predictions = set()
#        for bp in bfast_brkpts:
#            bfast_predictions.add(bp[0])
#        # do the breaks we found agree with timesync data?
#        break_number_covered = 0
#        for bf_element in bfast_brkpts:
#            bf_time = bf_element[0] + bf_element[1]/365.
#            for gth_element in ground_truth_bps[break_number_covered:]:
#                ts_time1 = gth_element[0]
#                ts_time2 = gth_element[1]
#                if (bf_time >= ts_time1 - eps) and (bf_time <= ts_time2 + eps):
#                    bfast_true_positives += 1
#                    break_number_covered += 1  # this is to prevent overcounting.
#                                               # Eg., there may be multiple alarms
#                                               # for just one event. Especially, with ltr.
#                    break
#        
#        # did we miss a break suggested in timesync data?
#        for gth_element in ground_truth_bps:
#            found = False
#            for j in range(gth_element[0]-1, gth_element[1]+2):
#                if j in bfast_predictions:
#                    # bfast did pick this up. So does not contribute to a miss.
#                    found = True
#                    bfast_predictions.discard(j)
#                    break
#            if found == False:
#                bfast_false_negatives += 1
#
#        ew_total_num_sigs += len(ewma_brkpts)
#        ewma_predictions = set()
#        for bp in ewma_brkpts:
#            ewma_predictions.add(bp[0])
#        # do the breaks we found agree with timesync data?
#        break_number_covered = 0
#        for ew_element in ewma_brkpts:
#            ew_time = ew_element[0] + ew_element[1]/365.
#            for gth_element in ground_truth_bps[break_number_covered:]:
#                ts_time1 = gth_element[0]
#                ts_time2 = gth_element[1]
#                if (ew_time >= ts_time1 - eps) and (ew_time <= ts_time2 + eps):
#                    ewma_true_positives += 1
#                    break_number_covered += 1
#                    break
#        # did we miss a break suggested in timesync data?
#        for gth_element in ground_truth_bps:
#            found = False
#            for j in range(gth_element[0]-1, gth_element[1]+2):
#                if j in ewma_predictions:
#                    found = True
#                    ewma_predictions.discard(j)
#                    break
#            if found == False:
#                ewma_false_negatives += 1
#
#        ltr_total_num_sigs += len(ltr_brkpts)
#        ltr_predictions = set()
#        for bp in ltr_brkpts:
#            ltr_predictions.add(bp[0])
#        
#        # do the breaks we found agree with timesync data?
#        break_number_covered = 0
#        for ltr_element in ltr_brkpts:
#            ltr_time = ltr_element[0] + ltr_element[1]/365.
#            for gth_element in ground_truth_bps[break_number_covered:]:
#                ts_time1 = gth_element[0]
#                ts_time2 = gth_element[1]
#                if (ltr_time >= ts_time1 - eps) and (ltr_time <= ts_time2 + eps):
#                    ltr_true_positives += 1
#                    break_number_covered += 1
#                    break
#        # did we miss a break suggested in timesync data?
#        for gth_element in ground_truth_bps:
#            found = False
#            for j in range(gth_element[0]-1, gth_element[1]+2):
#                if j in ltr_predictions:
#                    found = True
#                    ltr_predictions.discard(j)  # to prevent same flag for two diferent
#                                                # events, especially, when events are 
#                                                # back to back.
#                    break
#            if found == False:
#                ltr_false_negatives += 1
#
#        poly_total_num_sigs += len(polyAlgo_brkpts)
#        polyAlgo_predictions = set()
#        for bp in polyAlgo_brkpts:
#            polyAlgo_predictions.add(bp[0])
#
#        # do the breaks we found agree with timesync data?
#        break_number_covered = 0
#        for poly_element in polyAlgo_brkpts:
#            poly_time = poly_element[0] + poly_element[1]/365.
#            for gth_element in ground_truth_bps[break_number_covered:]:
#                ts_time1 = gth_element[0]
#                ts_time2 = gth_element[1]
#                if (poly_time >= ts_time1 - eps) and (poly_time <= ts_time2 + eps):
#                    polyAlgo_true_positives += 1
#                    break_number_covered += 1
#                    break
#        # did we miss a break suggested in timesync data?
#        for gth_element in ground_truth_bps:
#            found = False
#            for j in range(gth_element[0]-1, gth_element[1]+2):
#                if j in polyAlgo_predictions:
#                    found = True
#                    polyAlgo_predictions.discard(j)
#                    break
#            if found == False:
#                polyAlgo_false_negatives += 1

    with open("polyalgo_distances.csv", "a") as fh:
        fh.write('ew: ' + str(ew) + ', bf: ' + str(bf) + ', ltr:' + str(ltr) + \
                    ', none: ' + str(nun) + ', insuffsicient: ' + str(insuff) + '\n')
        fh.write('num true brks = ' + str(num_true_brks) + '\n')
        fh.write('ew_TP = ' + str(ewma_true_positives) + '\n')
        fh.write('ew_FN = ' + str(ewma_false_negatives) + '\n')
#        fh.write('ew_FP = ' + str(ew_total_num_sigs - ewma_true_positives) + '\n')
        fh.write('ltr_TP = ' + str(ltr_true_positives) + '\n')
        fh.write('ltr_FN = ' + str(ltr_false_negatives) + '\n')
#        fh.write('ltr_FP = ' + str(ltr_total_num_sigs - ltr_true_positives) + '\n')
        fh.write('bf_TP = ' + str(bfast_true_positives) +'\n')
        fh.write('bf_FN = ' + str(bfast_false_negatives) + '\n')
#        fh.write('bf_FP = ' + str(bf_total_num_sigs - bfast_true_positives) + '\n')
        fh.write('poly_TP = ' + str(polyAlgo_true_positives) + '\n')
        fh.write('poly_FN = ' + str(polyAlgo_false_negatives) + '\n')
#        fh.write('poly_FP = ' + str(poly_total_num_sigs - polyAlgo_true_positives) + '\n')
        fh.write('num_change_pixels =' + str(num_change_pixels) + '\n')
        fh.write('change_bf_says_change =' + str(change_bf_says_change) + '\n')
        fh.write('change_bf_says_stable =' + str(change_bf_says_stable) + '\n')
        fh.write('change_ew_says_change =' + str(change_ew_says_change) + '\n')
        fh.write('change_ew_says_stable =' + str(change_ew_says_stable) + '\n')
        fh.write('change_ltr_says_change =' + str(change_ltr_says_change) + '\n')
        fh.write('change_ltr_says_stable =' + str(change_ltr_says_stable) + '\n')
        fh.write('change_poly_says_change =' + str(change_poly_says_change) + '\n')
        fh.write('change_poly_says_stable =' + str(change_poly_says_stable) + '\n')
        fh.write('num_stable_pixels =' + str(num_stable_pixels) + '\n')
        fh.write('stable_bf_says_stable =' + str(stable_bf_says_stable) + '\n')
        fh.write('stable_bf_says_change =' + str(stable_bf_says_change) + '\n')
        fh.write('stable_ew_says_stable =' + str(stable_ew_says_stable) + '\n')
        fh.write('stable_ew_says_change =' + str(stable_ew_says_change) + '\n')
        fh.write('stable_ltr_says_stable =' + str(stable_ltr_says_stable) + '\n')
        fh.write('stable_ltr_says_change =' + str(stable_ltr_says_change) + '\n')
        fh.write('stable_poly_says_stable =' + str(stable_poly_says_stable) + '\n')
        fh.write('stable_poly_says_change =' + str(stable_poly_says_change) + '\n')
        for fn_pid in fn_pids:
            fh.write(str(fn_pid) + '\n')

    fh.close()
    
    return

#
#
## collect all pids from conus_spectral.csv
#fn = '/home/rishu/research/thesis/myCodes/thePolyalgorithm/conus_spectrals.csv'
#mat_all_timeseries = defaultdict(list)
#with open(fn, 'r') as f:
#    first_line = f.readline()
#    for i, line in enumerate(f):
#        this_line = line.strip().split(',')
#        mat_all_timeseries[int(this_line[1])].append(line)
#        pass

# collect all pids from ts_disturbance_segments.csv. These are change pids.
#fn = '/home/rishu/research/thesis/myCodes/thePolyalgorithm/ts_disturbance_segments.csv'
#validation_pid_list = []
#with open(fn, 'r') as f:
#    first_line = f.readline()
#    for i, line in enumerate(f):
#        this_line = line.strip().split(',')
##        print this_line
#        pid = int(this_line[0])
#        if pid not in validation_pid_list:  # get unique pids only
#            validation_pid_list.append(pid)
#        pass
#f.close()

## write these pids to a separate file. Just like that.
#fn = '/home/rishu/research/thesis/myCodes/thePolyalgorithm/ts_disturbace_segments.csv'
#with open(fn, 'w') as fh:
#    for pid in validation_pid_list:
#            fh.write(str(pid) + '\n')
#    pass
#fh.close()

# pids that are present in conus spectrals but not in ts_disturbance_segments
# apparently never had a change in the 30 year period. Take them as stable pids.
#fn = '/home/rishu/research/thesis/myCodes/thePolyalgorithm/conus_allStable_pids.csv'
#with open(fn, 'w') as fh:
#    for key in mat_all_timeseries.keys()[1:]:
#        if key not in validation_pid_list:
#            fh.write(str(key) + '\n')
#        pass
#fh.close()

##=========================================================
## Then there are pids which are present in ts_disturbance_segments.csv but
## the change is in a period different outside of 2000-12. To list these pids
## do this: change_pid_list was generated above. For each pid in change_pid_list
## check if there was a change in 2000-12 period. If no, count it as stable.
#fn_groundTruth = '/home/rishu/research/thesis/myCodes/thePolyalgorithm/ts_disturbance_segments.csv'
#stable_pids = []
#time_start = 1990
#time_end = 2012
#for my_pid in validation_pid_list:
#    mat_all_changes_for_fixed_pixel = []
#    with open(fn_groundTruth, 'r') as f_gt:
#        first_line = f_gt.readline()
#        for i, line in enumerate(f_gt):
#            this_line = line.strip().split(',')
#            if int(this_line[0]) == my_pid:
#                mat_all_changes_for_fixed_pixel.append(line)
#            pass
#    
#    num_changes = 0
#    changes = []
#    # Note that if pid is a no-disturbance-ever pixel, then mat_all_changes will be empty anyways.
#    # So this loop won't run. 
#    # So, basically, the 'else' statement in the loop gets executed only for pids where some lu-cover info is available.
#    for line in mat_all_changes_for_fixed_pixel:
#        mat_gt_vals = line.strip().split(',')
#        s_yr = mat_gt_vals[1]
#        e_yr = mat_gt_vals[2]
#        s_lu = mat_gt_vals[5]
#        e_lu = mat_gt_vals[6]
#        if ((int(s_yr) >= time_start) and (int(e_yr) <= time_end)):
#            num_changes +=1
#            change_type = mat_gt_vals[3]
#            changes.append([s_yr, e_yr, change_type, s_lu, e_lu])
#        else:
#            changes.append(['x','x','x', s_lu, e_lu])
#    changes = [num_changes] + changes
#    
#    # Now check the number of changes in 2000-12. If there is no change, list is as stable.
#    if changes[0] == 0:
#        stable_pids.append(my_pid)
#
#fn = '/home/rishu/research/thesis/myCodes/thePolyalgorithm/ts_1990to12_stable_pids.csv'
#with open(fn, 'w') as fh:
#    for my_pid in stable_pids:
#        with open(fn_groundTruth, 'r') as f_gt:
#            first_line = f_gt.readline()
#            for i, line in enumerate(f_gt):
#                this_line = line.strip().split(',')
#                if int(this_line[0]) == my_pid:
#                    fh.write(line)
#                pass
#        f_gt.close()
#fh.close()
#
##=========================================================
## Now separate forest and nonForest 2000-12 stable pixels


# We limit ourselves to the pids mentioned in ts_disturbance_segments.csv.
# The pids present in ts_disturbance_segments.csv have change at some point in 
# 1984-2014 time period. They may or may not have a
# change in 2000-12 time period. If they have a change in 2000-12 time period, they form
# change pids for us. Write change pids to a different file. Two different
# cases are considered: Forest-change, and Nonforest change.
#fn = '/home/rishu/research/thesis/myCodes/thePolyalgorithm/ts_disturbance_segments.csv'
#nflines_list = []
#with open(fn, 'r') as f:
#    first_line = f.readline()
#    for i, line in enumerate(f):
#        this_line = line.strip().split(',')
##        if ( this_line[5][0:3] != 'FOR'  and  \
#        if ( int(this_line[1]) > 1990  and int(this_line[2]) < 2012 ) :
##            print int(this_line[0]), ', ', this_line[1], ', ', this_line[5]
#            pid = int(this_line[0])
#            nflines_list.append(line)
#        pass
#f.close()
#
#fn_change = '/home/rishu/research/thesis/myCodes/thePolyalgorithm/ts_change_pids_1990to12.csv'
#with open(fn_change, 'w') as fw:
#    for line in nflines_list:
#        fw.write(str(line))
#fw.close()

## All nonforest pixel in ts_disturbance_segments.csv
#with open('/home/rishu/research/thesis/myCodes/thePolyalgorithm/ts_change_pids_nonforest.csv', 'w') as fw:
#    for line in nflines_list:
#        fw.write(str(line))
#fw.close()

## the pids present in conus_spectrals and absent in timeSync_pids_change are stable pids
## write them to a separate file
#fn_stable = '/home/rishu/research/thesis/myCodes/thePolyalgorithm/timeSync_pids_stable.csv'
#with open(fn_stable, 'w') as fw:
#    for pid in px_list:
#        if pid in change_pid_list:
#            a = 1
#        else:
#            fw.write(str(pid) + '\n')
#fw.close()


## collect all flood impacted pids from ts_disturbance_segments.csv and write them to a separate file
#fn = '/home/rishu/research/thesis/myCodes/thePolyalgorithm/ts_disturbance_segments.csv'
#water_lines_list = []
#with open(fn, 'r') as f:
#    first_line = f.readline()
#    for i, line in enumerate(f):
#        this_line = line.strip().split(',')
#        if (int(this_line[1]) in range(2000,2013)  \
#              and int(this_line[2]) in range(2000, 2013) \
#              and this_line[3] == 'Water'):
#            print int(this_line[1]), ', ', this_line[5], ', ', this_line[6]
#            pid = int(this_line[1])
#            water_lines_list.append(line)
#        pass
#f.close()
#
#with open('/home/rishu/research/thesis/myCodes/thePolyalgorithm/timeSync_pids_flood.csv', 'w') as fw:
#    for line in water_lines_list:
#        fw.write(str(line))
#fw.close()

# collect all fire impacted pids from ts_disturbance_segments.csv and write them to a separate file
#fn = '/home/rishu/research/thesis/myCodes/thePolyalgorithm/ts_disturbance_segments.csv'
#fire_lines_list = []
#with open(fn, 'r') as f:
#    first_line = f.readline()
#    for i, line in enumerate(f):
#        this_line = line.strip().split(',')
#        if (int(this_line[1]) in range(2000,2013)  \
#              and int(this_line[2]) in range(2000, 2013) \
#              and this_line[3][0:3] == 'Fir'):
#            print int(this_line[1]), ', ', this_line[5], ', ', this_line[6]
#            pid = int(this_line[1])
#            fire_lines_list.append(line)
#        pass
#f.close()
#
#with open('/home/rishu/research/thesis/myCodes/thePolyalgorithm/timeSync_pids_fire.csv', 'w') as fw:
#    for line in fire_lines_list:
#        fw.write(str(line))
#fw.close()

## collect all fire impacted pids from ts_disturbance_segments.csv and write them to a separate file
#fn = '/home/rishu/research/thesis/myCodes/thePolyalgorithm/ts_disturbance_segments.csv'
#fire_lines_list = []
#with open(fn, 'r') as f:
#    first_line = f.readline()
#    for i, line in enumerate(f):
#        this_line = line.strip().split(',')
#        if (int(this_line[1]) in range(2000,2013)  \
#              and int(this_line[2]) in range(2000, 2013) \
#              and this_line[3][0:3] == 'Fir') or
#           (int(this_line[1]) in range(2000,2002)  \
#              and this_line[3][0:3] == 'Sit'):
#            print int(this_line[1]), ', ', this_line[5], ', ', this_line[6]
#            pid = int(this_line[1])
#            fire_lines_list.append(line)
#        pass
#f.close()
#
#with open('/home/rishu/research/thesis/myCodes/thePolyalgorithm/timeSync_pids_fire.csv', 'w') as fw:
#    for line in fire_lines_list:
#        fw.write(str(line))
#fw.close()

## collect all 'urbanized' pids from ts_disturbance_segments.csv and write them to a separate file
#fn = '/home/rishu/research/thesis/myCodes/thePolyalgorithm/ts_disturbance_segments.csv'
#urbn_lines_list = []
#with open(fn, 'r') as f:
#    first_line = f.readline()
#    for i, line in enumerate(f):
#        this_line = line.strip().split(',')
#        if (int(this_line[1]) in range(2000,2013)  \
#              and int(this_line[2]) in range(2000, 2013) \
#              and this_line[6][0:3] == 'NVA'):
#            print int(this_line[1]), ', ', this_line[5], ', ', this_line[6]
#            pid = int(this_line[1])
#            urbn_lines_list.append(line)
#        pass
#f.close()
#
#with open('/home/rishu/research/thesis/myCodes/thePolyalgorithm/timeSync_pids_urbanization.csv', 'w') as fw:
#    for line in urbn_lines_list:
#        fw.write(str(line))
#fw.close()

# collect all 'harvest' pids from ts_disturbance_segments.csv and write them to a separate file
#fn = '/home/rishu/research/thesis/myCodes/thePolyalgorithm/ts_disturbance_segments.csv'
#harvest_lines_list = []
#with open(fn, 'r') as f:
#    first_line = f.readline()
#    for i, line in enumerate(f):
#        this_line = line.strip().split(',')
#        if (int(this_line[1]) in range(2000,2013)  \
#              and int(this_line[2]) in range(2000, 2013) \
#              and this_line[3][0:3] == 'Har'):
#            print int(this_line[1]), ', ', this_line[5], ', ', this_line[6]
#            pid = int(this_line[1])
#            harvest_lines_list.append(line)
#        pass
#f.close()
#
#with open('/home/rishu/research/thesis/myCodes/thePolyalgorithm/timeSync_pids_harvest.csv', 'w') as fw:
#    for line in harvest_lines_list:
#        fw.write(str(line))
#fw.close()

# collect all 'harvest' pids from ts_disturbance_segments.csv and write them to a separate file
#fn = '/home/rishu/research/thesis/myCodes/thePolyalgorithm/ts_disturbance_segments.csv'
#anyChange00to12_lines_list = []
#with open(fn, 'r') as f:
#    first_line = f.readline()
#    for i, line in enumerate(f):
#        this_line = line.strip().split(',')
#        if (int(this_line[1]) in range(2000,2013)  \
#              and int(this_line[2]) in range(2000, 2013)):
#            print int(this_line[1]), ', ', this_line[5], ', ', this_line[6]
#            pid = int(this_line[1])
#            anyChange00to12_lines_list.append(line)
#        pass
#f.close()
#
#with open('/home/rishu/research/thesis/myCodes/thePolyalgorithm/timeSync_pids_anyChange00to12.csv', 'w') as fw:
#    for line in anyChange00to12_lines_list:
#        fw.write(str(line))
#fw.close()