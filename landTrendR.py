# -*- coding: utf-8 -*-
"""
Created on Fri Aug 12 20:04:21 2016

This version created on Oct 6 19:21:18 2016

@author: rishu
"""

import numpy as np
import scipy.special as splfn
import l2appr as myb
import copy
from commons import regress

missing_data_vals = -2222

def despike(vec_timestamps, vec_obs, despike_tol):
    
    """ 
    Step 1 in the pseudocode:
        isolated, single spikes in observvations are assumed to be faulty observations.
        These are detected and corrected divided differences.
        
    Output:
        vec_obs_updated:  numpy array of corrected observations.
    """

    vec_obs_updated = np.asarray(vec_obs, dtype='float')
    Sfinal = len(vec_timestamps)
    
#    if despike_tol > 1:
#        despike_tol = 1.0 #0.9
    prop = 1.0
    count = 0

    while (prop > despike_tol) and (count <= Sfinal):
        fwd_diffs = [-9999] + [vec_obs_updated[i+1]-vec_obs_updated[i] for i in range(1,Sfinal-1)] + [-9999]
        bkwd_diffs = [-9999] + [vec_obs_updated[i]-vec_obs_updated[i-1] for i in range(1, Sfinal)] + [-9999]
        central_diffs = [-9999] + [abs(vec_obs_updated[i+1]-vec_obs_updated[i-1]) for i in range(1,Sfinal-1)] + [-9999]
        prop_correction = [0 for i in range(Sfinal)]
        correction = [0 for i in range(0, Sfinal)]
        for i in range(1, Sfinal-1):     #no correctoin at the ends
            md = np.max(np.abs([fwd_diffs[i], bkwd_diffs[i]]))
            # what if both are zero?
            if md <= np.finfo(float).eps:
                md = central_diffs[i]
            #what if central_diffs is also 0? Then we have a 0/0 form.
            #then correction = 0 becuz rhs of correction formula is 0.
            if md == 0:
                correction[i] = 0
            else:
                prop_correction[i] = 1.0 - (abs(central_diffs[i])/float(md))
                correction[i] = prop_correction[i] * 0.5 * (vec_obs_updated[i+1] - \
                                2.0*vec_obs_updated[i] + vec_obs_updated[i-1])
        
        #max value is found excluding 1st and last position.
        prop = max(prop_correction[1:Sfinal-1]) 
        prop_ind = [i for i, x in enumerate(prop_correction) if x == prop]
        for i in prop_ind:
            vec_obs_updated[i] = vec_obs_updated[i] + correction[i]
        count = count + 1

    return vec_obs_updated
    
def scoreSegments(vec_timestamps, vec_obs, vertices, currNumVerts):
    """
    Step 2_support in the pseudocode:
        For each interval determined by the vertices given in 'vertices',
        calculate the least squares fit. 
        Then calculate the MSE for that interval.
        The score of a segment (or interval) is the MSE with that fit.
    
    Input: 
        timestamps, observations, vertices, and currNumVerts = len(vertices)
        
    Output:
        segmentScores: a list of MSEs, one MSE per interval.
    
    """
    
    segmentScores = []
    for i in range(0, currNumVerts-1):
        startInd = vertices[i]
        endInd = vertices[i+1]
        span = endInd - startInd + 1
        if (span > 2):
            yvals = vec_obs[startInd:endInd+1]
            xvals = vec_timestamps[startInd:endInd+1]
            #if we've done desawtooth, it's possible that all of the values in a
            #segment have the same value, in which case regress would choke.
            #So deal with that.
            if (max(yvals) - min(yvals) > 0):
                ycoeffs, fit = regress(xvals, yvals, "linear", 0)
            else:
                fit = yvals
                
            sqError = (yvals - fit)*(yvals - fit)
            segmentScores.append((sum(sqError))/span)
        else:
        # if vertex_i and vertex_{i+1} are really really right next to each other
        # then, we can't split that interval further anyways. So set the MSE for 
        # such an interval equal to 0, then the other interval will get chosen
        # for the next steps (of splitting etc).
        # This situation will arise, for example, when there is a 'sharp' drop
        # in values. Check out the figures in ISPRS paper.
            segmentScores.append(0)

    return segmentScores


def splitSeries(vec_timestamps, vec_obs, endSegment, distTest):
    
    """
    Step 2_support in the pseudocode:
        least squares fit is done on the current interval.
        pointwise error is calculated.
        the index corresponding to maximum pointwise error is returned.
        
    Output:
        maxDiffInd:  the index corresponding to maximum pointwise error is returned.
    
    """

    maxDiffInd = 0
    ok = False    
    S = len(vec_timestamps)
    coeffs, fit = regress(vec_timestamps, vec_obs, "linear", 0)
    diff = [abs(vec_obs[i] - fit[i]) for i in range(S)]
    diff[0] = 0
    diff[S-1] = 0 #end points are already vertices. So take them out of consideration
    
    if (distTest) and (endSegment) :
        if (vec_obs[S-1] <= vec_obs[S-2]):
            diff[S-2] = 0
        
    maxDiffInd = diff.index(max(diff))
    
    if (maxDiffInd > 0):
        ok = True    
    # if maxDiff occurs at an interior index, then we will accept it. Otherwise we'll look for sth else.
    return maxDiffInd, ok


def getInitVerts(vec_timestamps, vec_obs, mpnp1, distwtfactor):
    
    """
    Step 2 of the pseudocode:
        Using least squares regression iteratively, determine a set of initial breakpoints.
    
    Approach: For the 'current' vertices, calculate the MSE for each segment.
              Take the ONE interval with HIGHEST MSE and split it into two at
              the point of highest deviation. Then calculate the MSEs again.
              Continue iteratively until numMaxVerts vertices are found.

    Helper functions:
        scoreSegments
        splitSeries
        
    Input: 
        vec_timestamps: array timepoints (x-coordinates) to be used.
        vec_obs:        array of observations (y-coordinates).
        mpnp1:          maximum number of segments desired.
        distwtfactor:   user defined parameter that decided whether disturbance in initial segments
                        should be considered or not.
    Output:
        vertices:  a list of indices representing the initial breakpoints to be used.
    
    """

    numObs = len(vec_obs)
    numMaxVerts = min(mpnp1, numObs-2)   #internal
    vertices = [0,numObs-1]
    currNumVerts = 2
    
    while (currNumVerts < numMaxVerts):
       #The score of a segment is basically the mse in that fit.
       #Send in the entire domain and score EACH segment. 
        mses = scoreSegments(vec_timestamps, vec_obs, vertices, currNumVerts)
        ok = False   #0
        while(ok == False):    #0):
            # Amongst ALL segments, find the segment that has highest MSE.
            if (max(mses) == 0):
                #bail if we can't get high enough without breaking recovery rule
                return vertices
                
            max_mse_ind = mses.index(max(mses))  #returns the first occurance of maxval
            isFirstSeg = (max_mse_ind == 0)
            isLastSeg = ( max_mse_ind == currNumVerts-2)
            if (distwtfactor == 0):
                distTest = False
            else:
                distTest = True
            #1. just use distweightfactor to determine if disturbance 
            #   should be considered in initial segments
            #2. Take the ONE interval with HIGHEST MSE and split it into two at
            #   the point of highest deviation. So this 'highest mse' interval
            #   is sent into splitSeries. Both endpoints are included.
            newVertInd, ok = splitSeries(
                        vec_timestamps[vertices[max_mse_ind]: vertices[max_mse_ind+1]+1],
                        vec_obs[vertices[max_mse_ind] : vertices[max_mse_ind+1]+1], 
                        isLastSeg, distTest)
            if (ok == False):
            #means, this interval yielded a preexisting vertex. So this segment is useless.
                mses[max_mse_ind] = 0   #look in the next "best" option

        # ok = True now. We have a "new" eligible vertex. Include this in out vertices set
        vertices.append(newVertInd + vertices[max_mse_ind] )
        vertices.sort()
        currNumVerts += 1

    # We been able to find as many vertices as were possible by now.
    # Return this set to the calling program.
    return vertices


def angleDiff(xcoords, ycoords, yrange, distwtfactor):
    
    """
    Step 3_support of the pseudocode:
    
   1. Need three points -- middle point is the one that gets the score
       the others are the ones preceding and following
   2. Note that ycoords needs to be scaled to the range of the whole
       trajectory for this to really be meaningful
   3. Distweightfactor helps determine how much weight is given to angles
       that precede a disturbance.  If set to 0, the angle difference is
       passed straighton.
   4. If disturbance (positive), give more weight

    """
    
    angle1 = np.arctan2([ycoords[1]-ycoords[0]],[xcoords[1]-xcoords[0]]) * 180 /np.pi
    angle2 = np.arctan2([ycoords[2]-ycoords[1]],[xcoords[2]-xcoords[1]]) * 180 /np.pi
    scaler = max([0, (ycoords[2]-ycoords[1])*distwtfactor/yrange]) + 1
    my_angle = (max(angle1, angle2) - min(angle1, angle2))*scaler
    
    return my_angle[0]


def cullByAngleChange(vec_timestamps, vec_obs, startingVerts, mu, nu, distwtfactor):
    
    """
    Step 3 of the pseudocode:
        Drop 'insignificant' vertices.
        Specifically, if the angle formed at a vertex is almost zero (or, 180),
        that vertex is not 'important' and is dropped.
        
    Input: 
        vec_timestamps, vec_obs: numpy arrays.
        startingVerts:           list of initial vertices.

    Helper function:
        angleDiff
        
    Output:
        currVerts:  an updated list of vertices 
    
    """
    
    # startingVerts : global indices (in vec_timestamps) of the points
    #                 that got chosen as indices.

    numCurrVerts = len(startingVerts)
    numVertsToRemove = numCurrVerts - (mu + 1)
    
   #if we don't have enough, just return what was given get initial slope ratios
   #across all points
    if ((numVertsToRemove < 0) or (numCurrVerts <= 3)):
        currVerts = copy.deepcopy(startingVerts)        
        return  currVerts
    
    #for angles, need to make it scaled in y like we see in display
    y_ran = max(vec_obs) - min(vec_obs)
    x_ran = max(vec_timestamps) - min(vec_timestamps)
    yscaled = [x_ran * (vec_obs[i] - min(vec_obs))/y_ran \
                                    for i in range(len(vec_obs))]
    yscaled_ran = max(yscaled) - min(yscaled)

    # calculate all angles (interior vertices only)
    currVerts = copy.deepcopy(startingVerts)
    angles = [0] * numCurrVerts
    for i in range(1, numCurrVerts-1):
        this_ind = currVerts[i]
        prev_ind = currVerts[i-1]
        next_ind = currVerts[i+1]
        angles[i] = angleDiff([vec_timestamps[prev_ind], vec_timestamps[this_ind], vec_timestamps[next_ind]], \
                    [vec_obs[prev_ind], vec_obs[this_ind], vec_obs[next_ind]], 
                     yscaled_ran, distwtfactor)
    # the angles at index 0 and -1 are redundant anyways. So just get rid of them!
    #del (angles[-1])
    #del (angles[0])
    
    # Now go through iteratively and remove them
    for i in range(numVertsToRemove):
        #pick from the slope diffs in play (not the ones at the end, which are 
        #shifted there from prior iterations)
        minAngleInd = angles[1:-1].index(min(angles[1:-1])) +1  #+1  for index in angles
        minVertInd = minAngleInd
        assert minAngleInd != len(angles) -1
        if (minAngleInd == len(angles)-2):
            # drop this vertex. update the endVertMarker
            del (currVerts[-2])
            
            # drop this angle. update the endAngMarker
            del (angles[-2])
            
            # recalculate the angle for the vertex to the left of the dropped one:
            angles[-2] = angleDiff([vec_timestamps[i] for i in currVerts[-3:]], 
                                    [vec_obs[i] for i in currVerts[-3:]], 
                                    yscaled_ran, distwtfactor)
        
        elif (minVertInd == 1):
            # drop this vertex. update the endVertMarker
            del (currVerts[1])
            
            # drop this angle. update the endAngMarker
            del (angles[1])
            
            # recalculate the angle to the right of the one taken out:
            angles[1] = angleDiff([vec_timestamps[i] for i in currVerts[0:3]], 
                                  [vec_obs[i] for i in currVerts[0:3]], 
                                   yscaled_ran, distwtfactor)
            
        else:
            # drop this vertex. update the endVertMarker
            del (currVerts[minVertInd])

            # drop this angle. update the endAngMarker
            del (angles[minAngleInd])
            
            # recalculate the angle to the left of the one taken out:
            angles[minAngleInd-1] = angleDiff([vec_timestamps[i] for i in currVerts[minVertInd-2:minVertInd+1]], 
                                  [vec_obs[i] for i in currVerts[minVertInd-2:minVertInd+1]],
                                   yscaled_ran, distwtfactor)
            
             # recalculate the angle to the right of the one taken out:
            angles[minAngleInd] = angleDiff([vec_timestamps[i] for i in currVerts[minVertInd-1:minVertInd+2]],
                                  [vec_obs[i] for i in currVerts[minVertInd-1:minVertInd+2]], 
                                   yscaled_ran, distwtfactor)

    return  currVerts


def pickBetterFit(vec_obs, fit1, fit2):
    
    """
    Step 4_support    
    """

    diff1 = [vec_obs[i] - fit1[i] for i in range(len(fit1))]
    diff2 = [vec_obs[i] - fit2[i] for i in range(len(fit2))]
    
    mse1 = np.dot(diff1, diff1)
    mse2 = np.dot(diff2, diff2)
    if (mse1 < mse2):
        return 'fit1'
    else:
        return 'fit2'


def anchoredRegress(xvals, yvals, yanchorval):
    """
    Step 4_support:
        
        Left end is fixed to yanchorval.
        Linear regression is then done to determine the slope of the fit in this current interval.
        
    Output:
        slope: slope of the fit in current interval
        fit:   fitted values.
    """

    x = xvals - xvals[0]
    y = yvals - yanchorval
    xy = np.dot(x, y)
    xx = np.dot(x, x)
    slope = xy/xx
    fit = [slope *xcoord + yanchorval  for xcoord in  x]
    return slope, fit


def findBestTrace(vec_timestamps, vec_obs, currVerts):
    """
    Step 4 of the pseudocode:
        
        For each interval, two fits are cosidered: (i) anchored regression, and (ii) end-points-connecting line.
        The fit with lesser MSE is chosen as the final fit.
        (In my opinion, anchored regression will always give lower MSE.)
        
    Helper functions:
        anchoredRegress, pickBetterFit.
    
    Output:
        bt:  a dictionary containing  vertices, vertYVals, yFitVals, and slopes of the calcualted model.

    """
#    Given set of vertices (x-vals), find the the combo of vertex y-vals
#    that results in best fit for each segment x and y are the original values.
#    vertices: is the list of vertices (in terms of array position, not the x-value).
#
#    "x values"
#    "y values"
#    "currVerts"
#    "x coords of vertices"
#    "y coords of vertices"
#    "y-fit values"
#    "slopes is needed for later analysis in the main algorithm. So we store and return those as well"
    Sfinal = len(vec_timestamps)
    numSegs = len(currVerts) - 1
    bt = {'vertYVals': 'null', 'yFitVals' : 'null','slopes' : 'null'}
    
    yFitVals = [0] * Sfinal
    yCoordsOfVerts = [vec_obs[i] for i in currVerts]
    slopes = [0] * numSegs
    # linear fit in the interval [t_1, t_{v_1}]
    seg = 1
    v1 = currVerts[0]
    v2 = currVerts[1]
    fillWay = np.interp( vec_timestamps[v1:v2+1] , \
              [vec_timestamps[v1], vec_timestamps[v2]], \
              [vec_obs[v1],vec_obs[v2]] )
    
    dummy, regressWay = regress(vec_timestamps[v1:v2+1], vec_obs[v1:v2+1], 'linear', 0)
    choice = pickBetterFit(vec_obs[v1:v2+1], fillWay, regressWay)
    
    if (choice == 'fit1'):
        yFitVals[v1: v2+1] = copy.deepcopy(fillWay)
        yCoordsOfVerts[seg-1] = fillWay[0]
        yCoordsOfVerts[seg] = fillWay[v2]
        slopes[seg-1] = (vec_obs[v2] - vec_obs[v1])/  \
                        (vec_timestamps[v2] - vec_timestamps[v1])        
    else:
        yFitVals[v1: v2+1] = copy.deepcopy(regressWay)
        yCoordsOfVerts[seg-1] = regressWay[0]
        yCoordsOfVerts[seg] = regressWay[v2]
        slopes[seg-1] = dummy[1]   # becuz that's how we had set up our matrix in regress.

    for seg in range(2, numSegs+1):
        v1 = currVerts[seg-1]
        v2 = currVerts[seg]
        fillWay = np.interp(vec_timestamps[v1:v2+1] , \
                          [vec_timestamps[v1],vec_timestamps[v2]],  \
                          [yCoordsOfVerts[seg-1], yCoordsOfVerts[seg]] )

        dummy, anchWay = anchoredRegress(vec_timestamps[v1:v2+1], \
                                     vec_obs[v1:v2+1], yCoordsOfVerts[seg-1])

        choice = pickBetterFit(vec_obs[v1:v2+1], fillWay, anchWay)

        if (choice == 'fit1'):
            #yFitVals[v1] will stay the same. Replacing it isn't really needed.
            yFitVals[v1: v2+1] = copy.deepcopy(fillWay)
            #actually, in this case, yCoordsOfVerts won't change. So no need
            #to update.
            #yCoordsOfVerts[seg-1] = fillWay[0]
            #yCoordsOfVerts[seg] = fillWay[-1]
            slopes[seg-1]= (vec_obs[v2]- vec_obs[v1])/(vec_timestamps[v2]- vec_timestamps[v1]) 
        else:
            #yFitVals[v1] will stay the same. Replacing it isn't really needed.
            yFitVals[v1: v2+1] = copy.deepcopy(anchWay)
            #yCoordsOfVerts[seg-1] = anchWay[0]     #will be same as before.
            yCoordsOfVerts[seg] = anchWay[-1]   #only this one needs to be updated.
            slopes[seg-1] = dummy   # becuz that's how we had set up our matrix in regress.
    bt = {'vertices': currVerts, 'vertYVals': yCoordsOfVerts, \
          'yFitVals' : yFitVals, 'slopes' : slopes}
    
    return bt


def calcFittingStats(vec_obs, vec_fitted, nParams):
    
    """
    Step 5 of the pseudocode:
        given the (i) observations, and (ii) a linear fit model get the 'goodness of fit'.
        F-statistics or p-of-F value may be used.
        
    Output:
        modelStats:    A dictionary with a bunch of statistics on the model.
    
    """
    
    nObs = len(vec_obs)
    nPred = len(vec_fitted)
    
    if (nObs != nPred):
        ok = 0
        return ok

    observed = copy.deepcopy(vec_obs)
    fitted = copy.deepcopy(vec_fitted)
    
    ubar = sum(observed)/nObs
    meanModel_errSquared = [(observed[i]-ubar)*(observed[i]-ubar) for i in range(nObs)]
    ss_mean = sum(meanModel_errSquared)
    resid = [abs(observed[i] - fitted[i]) for i in range(0, nObs)]    
    abs_diff = sum(resid)
    ss_resid = sum([r*r for r in resid])
    
    X1_squared = ss_mean - ss_resid
    X2_squared = ss_resid
    
    dof1 = nParams 
    dof2 = nObs - (nParams +1)  
    if (dof2 <= 0):
        modelStats = {'ok': 0,
                      'mean_u': ubar,
                      'sum_of_squares': ss_mean ,
                      'sum_of_squares_resids':  X2_squared ,
                      'sum_of_squares_regressor': X1_squared,
                      'dof1': dof1,
                      'dof2': dof2,
                      'fstat':  0,
                      'p_of_f': 1,
                      'aicc':  0,
                      'residual_variance':  0,
                      'total_variance':  0 ,
                      'adjusted_rsquare': 0 ,
                      'ms_resid': 0,
                      'ms_regr': 0,
                      'yfit':  vec_fitted,
                      'abs_diff': abs_diff,}
        
    else:
        residual_variance = ss_resid/dof2
        total_variance = ss_mean/(nObs-1)
        adjusted_rsquared = 1 - (residual_variance / total_variance)
        
        ms_regr = X1_squared/dof1
        if (ms_regr < 0.00001):
            f = 0.0001
        else:
            f = (X1_squared/dof1)/(X2_squared/dof2)
            
        ms_resid = X2_squared/dof2
        # Get the probability that F > f, i.e., Q(f| d1, d2)
        # We get Ix. p_of_f is 1.0 - Ix.
        pval = splfn.betainc( 0.5 * dof2, 0.5 * dof1 , dof2/(dof2 + dof1*f) )  
        aic = (2.0 * nParams) + (nObs * np.log(X2_squared/nObs))
        aicc = aic + ((2.0 * nParams*(nParams+1))/(nObs - nParams -1))
        modelStats = {'ok': 1,
                      'mean_u': ubar,
                      'sum_of_squares': ss_mean ,
                      'sum_of_squares_resids':  X2_squared ,
                      'sum_of_squares_regressor': X1_squared,
                      'dof1': dof1,
                      'dof2': dof2,
                      'fstat':  f,
                      'p_of_f': 1.0 - pval,
                      'aicc':  aicc,
                      'residual_variance':  residual_variance,
                      'total_variance':  total_variance,
                      'adjusted_rsquare': adjusted_rsquared,
                      'ms_regr': ms_regr,
                      'ms_resid': ms_resid,
                      'yfit':  vec_fitted,
                      'abs_diff': abs_diff}
                      
    return modelStats


def takeOutWeakest(currModel, threshold, vec_timestamps, vec_obs, v, vertVals):
    
    """
    Step 6(i) of the pseudocode:
        
    Approach:
        Weakest segment is the segment with maximum absolute slope.
        Weakest vertex is the left vertex of this segment.

    Inputs:
        currModel:      a dictionary describing the model being evaluated
        threshold:      recovery_threshold
        vec_timestamps: the x-coordinate vector
        vec_obs:        the y-coordinate vector
        v:              indexes of the x-coords wrt vec_timestamps
        vertVals:       y-coordinates at the vertices
    
    Exactly 1 vertex will get dropped. So ---
    remVerts, remVertsVals: each have nVerts-1 elements,
    newSlopes:              has nVerts-2 elements,
    newFit:                 has same number of elements as x.
    
    Output:
        updatedVerts:   list of vertices after the 'weakest' vertex has been dropped.
        
    """

    nSlopes = len(currModel['slopes'])
    nVerts = len(v)
    updatedVerts = copy.deepcopy(v)
##   we operate under the knowledge that disturbance is always considered to have a
##   positive slope, and recovery a negative slope (based on band5 type indicators).
#    negatives = [i for i in range(nSlopes) if  \
#                ((currModel['slopes'][i] < 0) and (currModel['slopes'][i] != -1))]
    negatives = [i for i in range(nSlopes) if  \
                ((currModel['slopes'][i] > 0) and (-1.0*currModel['slopes'][i] != -1))]
    nNegatives = len(negatives)
    range_of_values = max(currModel['yfit']) - min(currModel['yfit'])

    if (nNegatives > 0):
        scaled_slopes = [abs(currModel['slopes'][i])/range_of_values for i in negatives]
    else:
        # set it so that it won't be greater than threshold. Then, MSE route gets executed.
        scaled_slopes = [threshold-1 for i in range(nSlopes)]
    
    run_mse = True
        
    if (max(scaled_slopes) >  threshold):
        #Note that scaled slopes has the absolute values of negative slopes.
        weakest_seg = negatives[scaled_slopes.index(max(scaled_slopes))]
        weakest_vertex = weakest_seg + 1
        #the violator is a segment -- which vertex to remove?
        #Since we are tracking through time we assume that it is the latter
        #vertex that is causing the problem and take it out. This will be
        #violated only if there are spikes in brightness that are not fixed
        #by desawtooth, but that situation would be no better removing the
        #first vertex anyway, so we stick with this approach since it will
        #take out more shadow problems. the only now nterpolate to get rid
        #of this point, so it doesn't mess up the fits later.
        if (weakest_vertex == nVerts - 1):
            # I have no clue how this helps!!
            vec_obs[v[weakest_vertex]] = vec_obs[v[weakest_vertex] - 1]
            vertVals[weakest_vertex] = vec_obs[v[weakest_vertex] ] # which is now the same as vec_obs[v[weakest_vertex] -1 ] ?!!
            #since the violating point was at end, need to run mse instead after fixing
            run_mse = True

        else:
            # we want to delete the vertex that form the right end of the weakest segment
            thisx = vec_timestamps[v[weakest_vertex]]
            leftx = vec_timestamps[v[weakest_vertex-1]]
            rightx = vec_timestamps[v[weakest_vertex+1]]
            lefty = vec_obs[v[weakest_vertex-1]]
            righty = vec_obs[v[weakest_vertex+1]]
            tmp = (righty - lefty)/(rightx - leftx)  # new slope?
            vec_obs[v[weakest_vertex]] = (thisx - leftx)*tmp + lefty
            
            del (updatedVerts[weakest_vertex])
            run_mse = False


    #If no neg. segment is found, or, the neg. segment cors to the last vertex, then
    #choose the vertex to be dropped based on MSE.
    if (run_mse == True):
        MSE = [99999999]
        for i in range(1,nVerts-1):
#            print i
            vleft = v[i-1]
            vright = v[i+1]
            leftx = vec_timestamps[v[i-1]]
            rightx = vec_timestamps[v[i+1]]
            lefty = vertVals[i-1]
            righty = vertVals[i+1]
            ptpfill = np.interp(vec_timestamps[vleft:vright+1], \
                                [leftx, rightx], [lefty, righty])
            vec_obs_local = vec_obs[vleft:vright+1]
            diff = [ptpfill[j] - vec_obs_local[j] for j in range(len(ptpfill))]
            MSE.append((sum(p*q for p,q in zip(diff, diff)))/(rightx - leftx))

        MSE.append(99999999)
        
        weakest_vertex = MSE.index(min(MSE[1:nVerts-1]))
        #Drop the weakest vertex
        del (updatedVerts[weakest_vertex])

    return updatedVerts
   

def pickBestModel(my_models, best_model_proportion, use_fstat, pval):
    """
    Step 7 of the pseudocode:
    Check each model for acceptability, and then return the index of the 'best' model.
    
    Inputs:
        my_models:  a list of models, where each element a dictionary representing/describing a model.
        
    Output:
        bestModelInd:  index of the best model in the above list.
        
    """
    
    numModels = np.size(my_models)
#    print 'useFstat =', use_fstat, ', bestModelProp =', best_model_proportion
    if (use_fstat == 0):
        #This is how we ideally want to choose our model. F-statistic in
        #comibination with it's p-value is more indicative.
        #Want to settle on a model that has low p of F-statistic
        mn = min([my_models[i]['p_of_f'] for i in range(numModels)])
        tau = (2.0 - best_model_proportion)*mn
        goodModelsInd = [i for i in range(numModels) if my_models[i]['p_of_f'] <= tau]
        bestModelInd = goodModelsInd[0]
    else:
        # Compromise: We'll make a choice based on F-statistic only. But, at least, we make
        # sure that we have some models that have p of F-statistic lower that a
        # certain threshold (pval).
        passTheTest = sum([1 for i in range(numModels) if my_models[i]['p_of_f'] <= pval])
        if (passTheTest == 0):
            bestModelInd = -1
            return bestModelInd
        #Now make a decision based on F-statistic only. What to do? :(            
        mx = max([my_models[i]['fstat'] for i in range(numModels)])
        tau = best_model_proportion * mx
        goodModelsInd = [i for i in range(numModels) if my_models[i]['fstat'] > tau]
        bestModelInd = goodModelsInd[0]
    
    return bestModelInd
    
    
def check_slopes(model, recovery_thresh):
    """
    Again, step 7 of the pseudocode:
        
        Once a model has been decided, this routine double checks the slopes in the model.
        We don't want the slopes to be 'abnormal'
        For e.g., a recovery steeper than a threshold may indicate unacceptability for the model.
        
    Input:
        model: a dictionary
        
    Output:
        accept: a string with value 'Yes' or 'No'
            
    """
    #given one model, look at its slopes
    #filter out if recovery happens quicker than quickest disturbance --
    #a value-free way to get unreasonable things out.
    #but of course don't do if all we have is recovery.  no way to tell for sure then
    
    accept = 'Yes'
    n_slopes = len(model['vertices']) - 1
    
    #all of these operate under the knowledge that
    #disturbance is always considered to have a negative 
    #slope, and recovery a positive slope (based on NDVI type indicators).
    #Always make sure that he adjustment factor that happens
    #upstream of find_segments6 ensures that recovery is negative
    #the original implementation has +ve/-ve the other way round, 
    #based on band 5 type indicators.

    #negatives = [i for i in range(n_slopes) if model['slopes'][i] < 0]
    positives = [i for i in range(n_slopes) if model['slopes'][i] > 0]
    range_of_vals = max(model['yfit']) - min(model['yfit'])
    if (len(positives) > 0):
#        scaled_slopes = [abs(model['slopes'][i])/range_of_vals for i in positives]
        scaled_slopes = [model['slopes'][i]/range_of_vals for i in positives]
        if (max(scaled_slopes) > recovery_thresh):
            accept = 'No'
            return accept

    return accept


def findBestTrace_alternate(vec_timestamps, vec_obs, currVerts):
    """
    Step 4' of the pseudocode:
        
    This routine is for the marquardt approach. Err ... actually, we are using Bsplines
   
    Place knots at the current vertices.
    Then fit get a fit using Bsplines approximation.
    Bsplines implementation is based on the corresponding Fortran codes from Prof. L.T.Watson, Prof. DeBoor.
 
    Inputs:
       vec_timestamps:  the x-coordinates
       vec_obs:         the observations (i.e., the y-coordinates)
       currVerts:       the current vertices.
   
    Output:
       bt:  a dictionary containing  
            vertices, vertYVals, yFitVals, and slopes of the calcualted model.
            (just as findBestTrace did.)
   
   """
#    "x values"
#    "y values"
#    "currVerts"
#    "x coords of vertices"
#    "y coords of vertices"
#    "y-fit values"
#    "slopes is needed for later analysis in the main algorithm. So we store and return those as well"

    numSegs = len(currVerts) - 1
    bt = {'vertices': 'null', 'vertYVals': 'null', 'yFitVals' : 'null','slopes' : 'null'}

    # order = degree + 1
    order = 2
    # Assuming that the vertices are labelled as \xi_1, \xi_2, ...., \xi_{l+1}. Then,
    numTotalVertices = len(currVerts)
    numInternalVertices = len(currVerts) - 2
    l = numTotalVertices - 1   # or, numInternalVertices + 1
    ktimesl = order * l
    ctntyCondsPerVertex = 1   # becuz landtrend only wants continuous. no imposition on derivatives.
    sum_ctntyCondsPerInternalVertex = numInternalVertices
    n_dim = ktimesl - sum_ctntyCondsPerInternalVertex

    Sfinal = len(vec_timestamps)        # number of data points
    knots = [vec_timestamps[0]] + [vec_timestamps[i] for i in currVerts] + [vec_timestamps[Sfinal-1]]

    weight = [1 for i in range(Sfinal)]

    bcoeff = myb.l2appr(n_dim, order, vec_timestamps, vec_obs, Sfinal, knots, weight)
    bcoeff_list = bcoeff.tolist()
    yfit = [0 for i in range(Sfinal)]
    for i in range(Sfinal):
        yfit[i] = myb.bvalue(vec_timestamps[i], bcoeff_list, 0, order, knots, n_dim)
        
    xCoordsOfVerts = [vec_timestamps[i] for i in currVerts]
    yCoordsOfVerts = [yfit[i] for i in currVerts]
    slopes = [0]*numSegs
    for i in range(numSegs):
        this_seg_slope = (yCoordsOfVerts[i+1] - yCoordsOfVerts[i])/(xCoordsOfVerts[i+1] - xCoordsOfVerts[i])
        slopes[i] = this_seg_slope

    bt = {'vertices': currVerts, 'vertYVals': yCoordsOfVerts, 'yFitVals' : yfit, 'slopes' : slopes}

    return bt


def takeOutWeakest_alternate(vec_timestamps, vec_obs, v, vertVals):
    
    """
    Step 6'(i)
    
    Unlike takeOutWeakest, we don't look for negative slopes anymore.

    Output:
        updatedVerts:   list of vertices after the 'weakest' vertex has been dropped.
                        (just like takeOutWeakest.)
    """
    
    nVerts = len(v)
    updatedVerts = copy.deepcopy(v)

    MSE = [99999999]
    for i in range(1,nVerts-1):
        vleft = v[i-1]
        vright = v[i+1]
        xleft = vec_timestamps[v[i-1]]
        xright = vec_timestamps[v[i+1]]
        yleft = vertVals[i-1]
        yright = vertVals[i+1]
        ptpfill = np.interp(vec_timestamps[vleft:vright+1], [xleft, xright], [yleft, yright])
        vec_obs_local = vec_obs[vleft:vright+1]
        diff = [ptpfill[j] - vec_obs_local[j] for j in range(len(ptpfill))]
        MSE.append((sum(p*q for p,q in zip(diff, diff)))/(xright - xleft))
    MSE.append(99999999)
    
    weakest_vertex = MSE.index(min(MSE[1:nVerts-1]))
    #Drop the weakest vertex
    del (updatedVerts[weakest_vertex])
        
    return updatedVerts
    

def get_alternate_models(vec_timestamps, vec_obs_despiked,\
                         newInitVerts, best_model_proportion, use_fstat, pval, \
                         recovery_threshold ):
    """
    Step 6' of the pseudocode:
        
        The entire 'alternate' iterative process of generated models is executed here.
        
        Outputs:
            my_alternate_models:   a list of models, each model being represented as a dictionary.
            bestModelInd:          the index corresponding the 'best' model in the above list.
    
    """
    
    my_alternate_models = []
    
    # Step 4': Fit trajectory using the marquardt approach. That's a global method in contrast
    #         to the above local method. (Actually ... this code uses Splines, instead.)
    model1_alternate = findBestTrace_alternate(vec_timestamps, vec_obs_despiked, newInitVerts)
    nSegs = len(newInitVerts) - 1
    nParams = nSegs
    model1_stats = calcFittingStats(vec_obs_despiked, model1_alternate['yFitVals'],  nParams)
    this_alternate_model = {'yfit':  model1_alternate['yFitVals'],
              'vertices': model1_alternate['vertices'],
              'fstat':  model1_stats['fstat'],
              'p_of_f':  model1_stats['p_of_f'],
               'aicc': model1_stats['aicc'],
              'vertYVals': model1_alternate['vertYVals'],
              'slopes' : model1_alternate['slopes']}

    my_alternate_models.append(this_alternate_model)

    prev_model_index = 0
    this_model_index = 1
    while (nSegs >1 ):

        updatedVertices_alternate = takeOutWeakest_alternate(vec_timestamps, vec_obs_despiked,
                                      my_alternate_models[prev_model_index]['vertices'],
                                      my_alternate_models[prev_model_index]['vertYVals'])

        updatedModel_alternate = findBestTrace_alternate(vec_timestamps, \
                                                         vec_obs_despiked, \
                                                         updatedVertices_alternate)

        nSegs = len(updatedModel_alternate['vertices']) - 1
        nParams = nSegs
        updatedModelStats_alternate = calcFittingStats(vec_obs_despiked, updatedModel_alternate['yFitVals'], nParams)
        this_alternate_model = {'yfit':  updatedModel_alternate['yFitVals'],
                      'vertices': updatedModel_alternate['vertices'],
                      'fstat':  updatedModelStats_alternate['fstat'],
                      'p_of_f':  updatedModelStats_alternate['p_of_f'],
                      'aicc': updatedModelStats_alternate['aicc'],
                      'vertYVals': updatedModel_alternate['vertYVals'],
                      'slopes' : updatedModel_alternate['slopes']}
        
        my_alternate_models.append(this_alternate_model)
        prev_model_index +=1
        this_model_index +=1

    #Pick best model
    accepted = False
    all_fstats = [my_alternate_models[i]['fstat'] for i in range(len(my_alternate_models))]  #becuz i need to do np.where on this.
    num_models_evaluated = 0
    while (accepted == False) and (num_models_evaluated < len(my_alternate_models)): #len(my_models) = \mu
        num_models_evaluated += 1
        #pickBestModel will choose the model with lowest p of F-statistic
        bestModelInd = pickBestModel(my_alternate_models, best_model_proportion, use_fstat, pval)
        if bestModelInd != -1:
            #check on the slopes: if the model has scaled slopes steeper than rec_thresh, 
            #we dont accept that model.
            accept = check_slopes(my_alternate_models[bestModelInd], recovery_threshold)
            if accept == 'No':
                my_alternate_models[bestModelInd]['p_of_f'] = 100000
                my_alternate_models[bestModelInd]['fstat'] = 0
                my_alternate_models[bestModelInd]['aicc'] = 0
                accepted = False  #redundant
            else:  #if accepted = 'yes' OR if none of the models is acceptable, then move on
                accepted = True
        else:
            # just use a single segment. Use the model that had minimum value of fstat
            bestModelInd = all_fstats.index(min(all_fstats))
            my_alternate_models[bestModelInd]['p_of_f'] = 1 #why are we resetting here?
            my_alternate_models[bestModelInd]['slopes'] = [0]
            mean_val = np.mean(vec_obs_despiked)
            tmp = my_alternate_models[bestModelInd]['vertYVals']
            my_alternate_models[bestModelInd]['vertYVals'] = [mean_val]*len(tmp)
            accepted = True
    
    return my_alternate_models, bestModelInd

def landTrend(tyeardoy, vec_obs_all, presInd, \
              ewma_trainingStart, ewma_trainingEnd, ewma_lowthreshold, ewma_K,\
              despike_tol, mu, nu, distwtfactor, recovery_threshold, \
              use_fstat, best_model_proportion, pval):
    
    """
    Algorithm LandTrendR.
    
    Inputs:
        tyeardoy:             A 2 column (numpy) matrix --- 1st column contains the years, the second
                              column contains the doys.
        vec_obs:              A 1 column numpy array. It contains spectral values (including missing)
                              for a fixed pixel and fixed band, in same chronological order as tyeardoy
        presInd:              numpy array containing the indices where vec_obs has is valid.
        despike_tol:          In despike step, spikes are dampened if the spectral value difference
                              between spectral values on either side of the spike is less than
        mu:                   Maximum number of segments allowed in the model.
        nu:                   The initial regression-based detection of potential vertices can overshoot
                              (max_segments + 1) vertices by this value.
        distwtfactor:         
        recovery_threshold:   During fitting, if a candidate segment has a recovery rate faster than
                              1/recovery_threshold (in years), that segment is disallowed and a threshold
                              different segmentation must be used. Setting to 1.0 turns off this filter.
        use_fstat:            0 means 'use p_of_f', '1' is for 'dont use p_of_f'.
                              So if use_fstat = 0, the code will use p_of_f
        pval:                 If best fitted trajectory's p-of-F value exceeds this threshold, the entire
                              trajectory is considered no-change.
            
            
        ewma_trainingStart, ewma_trainingEnd, ewma_lowthreshold, ewma_K: parameters for EWMACD. These are
        used to decide whether there is sufficient data for that pixel to do any processing. Redundant
        here now because this calculation has been moved to poly_1D.py, where presInd is calculated 
        and simply passed into each component algorithm.
        
    Outputs:
        bestModelInd:       the index of the 'best' model in the list my_models.
        my_models:          list of all models generated by the algorithm for this pixel.
                            One of these models (the one at bestModelInd index) is the final model.
                            Redundant output.
        brkptsGI:           List of breakpoints, each breakpoint being represented by its global index.
        brkPtYrDoy:         List of breakpoints, each breakpoint being described as [year, doy].
        vecTrendFitFull:    piecewise linear approximation to the trend.
                            original output of the algorithm. 
                            Redundant as of now in the LULC with polyalgo sense.
        brkpt_summary:      brkptsummary is needed in these 1D codes to make 1D plots. But for 2D, it is redundant.
        
    """

    num_obs = len(vec_obs_all)
    # ************* develop the presInd vector ***********************
#    presInd = np.where(vec_obs_all > ewma_lowthreshold)[0]
##    presInd_ltr = np.where(vec_obs_all > ewma_lowthreshold and tyeardoy[:, 1] >= 196 \
##                           and tyeardoy[:, 1] <= 243)[0]
#    tyeardoy_idxs = np.where(np.logical_and(ewma_trainingStart<= tyeardoy[:,0], \
#                                            tyeardoy[:,0]< ewma_trainingEnd))[0]
#    common_idx = list(set(tyeardoy_idxs).intersection(presInd))
#    training_t = tyeardoy[common_idx, 1]
#
#    #Corner case
#    if (len(training_t) < 2 * ewma_K + 1):    #from ewmacd
#        brkPtsGlobalIndex = [0, num_obs-1]
#        brkPtYrDoy = [tyeardoy[i,:] for i in brkPtsGlobalIndex]
#        bestModelInd = -9999
#        my_models = []
#        vecTrendFitFull = [missing_data_vals]*num_obs
#        brkpt_summary = [missing_data_vals]*num_obs
#        return bestModelInd, my_models, brkPtsGlobalIndex, brkPtYrDoy, vecTrendFitFull, brkpt_summary #, [], []
    
    ind = 0
    num_days_gone = 0
    vec_timestamps_edited = np.zeros(num_obs)
    vec_timestamps_edited[0] = tyeardoy[ind, 1]
    while ind < num_obs:
        if ind > 0:
            if (tyeardoy[ind,0] != tyeardoy[ind-1, 0]):
                if (tyeardoy[ind-1, 0] % 4) == 0:
                    num_days_gone = num_days_gone + 366
                else:
                    num_days_gone = num_days_gone + 365
                    
                vec_timestamps_edited[ind] = num_days_gone + tyeardoy[ind, 1]
            else:
                vec_timestamps_edited[ind] = num_days_gone + tyeardoy[ind, 1]
                
        ind += 1

    #*************** prepare data ***********************************
    vec_timestamps = vec_timestamps_edited[presInd] # in original implementation, this is a subset of presInd.
#                                                     Only summer indices are included.
    vec_obs = vec_obs_all[presInd]
    summer_pres_indices = presInd
#    doy_start = 181
#    doy_end = 243
#    vec_timestamps, vec_obs, summer_pres_indices = \
#              getDataSubset(tyeardoy, vec_timestamps_edited, vec_obs_all, presInd, \
#                                            doy_start, doy_end)

    #*********** actual processing starts here **********************
    my_models = []

    #despike
    vec_obs_despiked = despike(vec_timestamps, vec_obs, despike_tol)
    
    mpnp1 = mu + nu + 1
    #Find potential breakpoints
    initVerts = getInitVerts(vec_timestamps, vec_obs_despiked, mpnp1, distwtfactor)

    #Cull by angle change
    newInitVerts = cullByAngleChange(vec_timestamps, vec_obs_despiked, initVerts, \
                                     mu, nu, distwtfactor)

    #Fit trajectory in this model. Aka, find first model. Also get it's goodness.
    model1 = findBestTrace(vec_timestamps, vec_obs_despiked, newInitVerts)

    #Note: IDL code uses an unnecessarily complicated expression for 
    #nSegs :o :( :/. But we do agree with them on the no. of parameters.
    nSegs = len(newInitVerts) - 1
    nParams = nSegs
    model1_stats = calcFittingStats(vec_obs_despiked, model1['yFitVals'],  nParams)
    this_model = {'yfit':  model1['yFitVals'],
              'vertices': model1['vertices'],
              'vertYVals': model1['vertYVals'],
              'slopes' : model1['slopes'],
              'fstat':  model1_stats['fstat'],
              'p_of_f':  model1_stats['p_of_f'],
               'aicc': model1_stats['aicc']}

    my_models.append(this_model)

    #Simplify (reduce) model, one vertex at a time, to generate \mu different models.
    prev_model_index = 0
    this_model_index = 1 
    while (nSegs >1 ):  #
        # step (i): update vertices
        updatedVertices = takeOutWeakest(my_models[prev_model_index], recovery_threshold,
                                      vec_timestamps, vec_obs_despiked,
                                      my_models[prev_model_index]['vertices'],
                                      my_models[prev_model_index]['vertYVals'])

        # step (ii): update trace (i.e., vertYals, yFit, slopes, and a copy of vertices)
        updatedModel = findBestTrace(vec_timestamps, vec_obs_despiked, updatedVertices)
        
        # step (iii): update statistics (everything except yfit is scalar. yfit is only a copy
        #         of the yfit from trace)
        nSegs = len(updatedModel['vertices']) - 1
        nParams = nSegs
        updatedModelStats = calcFittingStats(vec_obs_despiked, updatedModel['yFitVals'], nParams)

        # step 4.: fill in the model        
        this_model = {'yfit':  updatedModel['yFitVals'],
                      'vertices': updatedModel['vertices'],
                      'vertYVals': updatedModel['vertYVals'],
                      'slopes' : updatedModel['slopes'],
                      'fstat':  updatedModelStats['fstat'],
                      'p_of_f':  updatedModelStats['p_of_f'],
                      'aicc': updatedModelStats['aicc']}
        my_models.append(this_model)
        prev_model_index +=1
        this_model_index += 1

    #Pick best model
    accepted = False
    all_fstats = [my_models[i]['fstat'] for i in range(len(my_models))]  #becuz i need to do np.where on this.
    num_models_evaluated = 0

    while (accepted == False) and (num_models_evaluated < len(my_models)): #len(my_models) = \mu
        num_models_evaluated += 1
        #pickBestModel will choose the model with lowest p of F-statistic
        bestModelInd = pickBestModel(my_models, best_model_proportion, use_fstat, pval)
        if bestModelInd != -1:
            #check on the slopes: if the model has scaled slopes steeper than rec_thresh, 
            #we dont accept that model.
            accept = check_slopes(my_models[bestModelInd], recovery_threshold)
            if accept == 'No':
                my_models[bestModelInd]['p_of_f'] = 10000
                my_models[bestModelInd]['fstat'] = 0
                my_models[bestModelInd]['aicc'] = 0
                accepted = False  #redundant
            else:  #if accepted = 'yes' OR if none of the models is acceptable, then move on
                accepted = True
        else:
            # just use a single segment. Use the model that had minimum value of fstat
            bestModelInd = all_fstats.index(min(all_fstats))
            accepted = True

    #############################################################################
    #############################################################################

    #If no good fit found, try the MPFITFUN approach (we are using Splines, instead!)
    if (my_models[bestModelInd]['p_of_f'] > pval):
        # redo the whole model generation part, this time with Levenberg-Marquardt algorithm based
        # fitting.
        # restart from vertices determined by vetVerts3
        # i.e., the vertices POST- cullByAngleChange.
        my_alternate_models, bestModelInd = get_alternate_models(vec_timestamps, vec_obs_despiked,\
                                              newInitVerts, best_model_proportion, use_fstat, pval, \
                                              recovery_threshold )
        my_models = copy.deepcopy(my_alternate_models)

    # get fit on the whole interval
    vecTrendFitFull = np.zeros(num_obs)
#    vecTrendFitFull[presInd] = my_models[bestModelInd]['yfit']
    vecTrendFitFull[summer_pres_indices] = my_models[bestModelInd]['yfit']
    vecTrendBrks = my_models[bestModelInd]['vertices']
#    brkptsGI = presInd[vecTrendBrks]
    brkptsGI = summer_pres_indices[vecTrendBrks]
    brkptsGI[0] = 0     # to account for any missing observations in the beginning
    brkptsGI[-1] = num_obs - 1   # to account for any missing observations at the end
    brkPtYrDoy = [tyeardoy[i,:] for i in brkptsGI]

    left = 0
    right = 1
    vertices =  my_models[bestModelInd]['vertices']  # same as vertices!!!
    numVerts = len(my_models[bestModelInd]['vertices'])
#    for i in range(presInd[0], presInd[-1]):
    for i in range(summer_pres_indices[0], summer_pres_indices[-1]):
        # Check if this location was present. If it was, we already have the value; no need
        # for further calculation.
#        if i in presInd:
        if i in summer_pres_indices:
            continue
        else:
            # locate the interval in which this x lies.
            while ((vec_timestamps_edited[i] >= vec_timestamps[vertices[right]])):
                left += 1
                right += 1
                if right >= numVerts-1:
                    break
            # Get the (x,y) coordinates of the segment representing this interval.
            x1 = vec_timestamps[vertices[left]]
            y1 = my_models[bestModelInd]['vertYVals'][left]
            x2 = vec_timestamps[vertices[right]]
            y2 = my_models[bestModelInd]['vertYVals'][right]
            # Then, y(x) = ((y2-y1)/(x2-x1)) * (x-x1) + y1
            vecTrendFitFull[i] = (float(y2-y1)/float(x2-x1))* \
                            (vec_timestamps_edited[i] - x1) + y1

    # getting values for points at the right end
    x1 = vec_timestamps[vertices[left]]
    x2 = vec_timestamps[vertices[right]]
    y1 = my_models[bestModelInd]['vertYVals'][left]
    y2 = my_models[bestModelInd]['vertYVals'][right]
    slope = float(y2-y1)/float(x2-x1)
    intercept = y1 - slope*x1 
#    for i in range(presInd[-1]+1, num_obs):
    for i in range(summer_pres_indices[-1]+1, num_obs):
        vecTrendFitFull[i] = slope * vec_timestamps_edited[i] + intercept

    # getting values for points at the left end
    x1 = vec_timestamps[vertices[0]]
    x2 = vec_timestamps[vertices[1]]
    y1 = my_models[bestModelInd]['vertYVals'][0]
    y2 = my_models[bestModelInd]['vertYVals'][1]
    slope = float(y2-y1)/float(x2-x1)
    intercept = y1 - slope*x1 
#    for i in range(0, presInd[0]):
    for i in range(0, summer_pres_indices[0]):
        vecTrendFitFull[i] = slope * vec_timestamps_edited[i] + intercept
    
    brkpt_summary = [0.0001 for i in range(num_obs)]
    for i in brkptsGI[1:-1]:
        brkpt_summary[i] = 1.0  #vecTrendFitFull[i] - vecTrendFitFull[i-1]

    return bestModelInd, my_models, brkptsGI, brkPtYrDoy , vecTrendFitFull, brkpt_summary
#brkptsummary is needed in these 1D codes to make 1D plots. But for 2D, it is redundant.
