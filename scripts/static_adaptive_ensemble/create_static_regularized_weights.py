#mcandrew

import sys
import numpy as np
import pandas as pd

from deviMM import *

def removeEnsembleModels(d):
    models = d.Model.unique()
    return d.loc[ ~d.Model.str.match("FSNetwork"),:]

def countNumberOfUniqueModels(d):
    return len(d.Model.unique())

def produceUniqueListOfSeasonsRegionsAndTargets(d):
    seasons = d.Season.unique()
    targets = d.Target.unique()
    regions = d.Location.unique()
    return seasons,regions,targets

def removeSeason(d,s):
    return d.loc[d.Season!=s,:]

def subsetTestSet2SpecificRegionTarget(d,r,t):
    return d.loc[(d.Target==t) & (d.Location==r),:]

def clip2TargetBounds(d,bounds):
    d = d.merge( bounds
                 ,left_on=['Season','Location','Target']
                 ,right_on=['Season','Location','Target'])
    d = d.loc[ (d['Model Week'] >= d['start_week_seq']) & (d['Model Week'] <= d['end_week_seq']),:]
    return d

def keepLogScoresAndTranspose(d):
    d = d.reset_index()
    d = pd.pivot_table(data = d
                       ,columns = ['Model']
                       ,values  = ['Score']
                       ,index   = ['Season','Location','Target','Epiweek']
    )
    models = [y for (x,y) in d.columns]
    return pd.DataFrame(np.matrix(d.values), columns = models)

def removeNALogScores(d):
    modelNames = logScoreData.columns 
    modelPis = {name:0. for name in modelNames}

    logScoreDataNoNA  = logScoreData.fillna(-10.0)
    modelNamesNoNA    = logScoreDataNoNA.columns
    return logScoreDataNoNA,modelNamesNoNA

def capLogScoresAtNeg10(d):
    d.loc[d.Score<-10,'Score']=-10.
    return d

def trainRegularizedStaticEnsemble(d,PRIOR):
    numberOfObservations, numberOfModels = d.shape
    priorWeightPerModel  = PRIOR*numberOfObservations/numberOfModels
    
    alphas,elbos =  deviMM(logScoreData.as_matrix()
                           ,priorPis = np.array(numberOfModels*[priorWeightPerModel])
                           ,maxIters = 10**2
                           ,relDiffThreshold = -1)
    return alphas

if __name__ == "__main__":

    singleBinLogScores = pd.read_csv('../../scores/scores.csv')
    singleBinLogScores = removeEnsembleModels(singleBinLogScores)

    targetBounds = pd.read_csv('./all-target-bounds.csv')

    numberOfModels = countNumberOfUniqueModels(singleBinLogScores)
    seasons,regions,targets = produceUniqueListOfSeasonsRegionsAndTargets(singleBinLogScores)
    seasons = list(seasons)
    seasons.append("2019/2020")

    priorPercent = 0.10 # HARD-CODED
    
    data = {'component_model_id':[],'season':[],'location':[],'target':[],'weight':[]}
    
    for season in seasons:
        testData = removeSeason(singleBinLogScores,season)

        for region in regions:
            for target in targets:
                sys.stdout.write('\x1b[2K\r Holdout:{:s}-Region={:s}-Target={:s}'.format(season,region,target))
                sys.stdout.flush()
                
                regionTargetData   = subsetTestSet2SpecificRegionTarget(testData,region,target)
                regionTargetData   = clip2TargetBounds(regionTargetData,targetBounds)
                regionTargetData   = capLogScoresAtNeg10(regionTargetData) 

                logScoreData     = keepLogScoresAndTranspose(regionTargetData) 
                
                logScoreData, modelNames = removeNALogScores(logScoreData)

                alphas = trainRegularizedStaticEnsemble(logScoreData,priorPercent)
                pis = alphas/sum(alphas)
                
                for (model,pi) in zip(modelNames, pis):
                    data['component_model_id'].append(model)
                    data['season'].append(season) 
                    data['location'].append(region)
                    data['target'].append(target)
                    data['weight'].append(float(pi))
    data = pd.DataFrame(data)
    data.to_csv('../../weights/static-regularized-target-region-weights.csv',index=False)
