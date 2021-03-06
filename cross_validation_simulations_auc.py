"""
Simple simulation code to reproduce figures on hight variance of
small-sample cross-validation.
"""

import pandas
import numpy as np
from scipy import ndimage

from joblib import Parallel, delayed, Memory
from sklearn.model_selection import (GroupShuffleSplit, RepeatedKFold, LeaveOneOut,
        cross_val_score, cross_val_predict)
from sklearn.metrics import roc_auc_score
from sklearn.svm import LinearSVC

def mk_data(n_samples=200, random_state=0, separability=1,
            noise_corr=2, dim=100):
    rng = np.random.RandomState(random_state)
    y = rng.random_integers(0, 1, size=n_samples)
    noise = rng.normal(size=(n_samples, dim))
    if not noise_corr is None and noise_corr > 0:
        noise = ndimage.gaussian_filter1d(noise, noise_corr, axis=0)
    noise = noise / noise.std(axis=0)
    # We need to decrease univariate separability as dimension increases
    centers = 4. / dim * np.ones((2, dim))
    centers[0] *= -1
    X = separability * centers[y] + noise
    return X, y

# create linearSVC that outputs continuous values for decision function for AUC
class LinearSVC_continuous(LinearSVC):
    def predict(self, X):
        return super(LinearSVC_continuous, self).decision_function(X)


###############################################################################
# Code to run the cross-validations

# below parameters tuned for AUC ~ 0.90, N=250, noise_corr=0, dim=300, sep=6.25
train_size = 250
noise_corr = 0
dim=300
sep=6.25
random_state=0

def sample_and_cross_val_clf(train_size=200, noise_corr=2, dim=3, sep=.5,
                             random_state=0):
    """ Runs an experiments and returns the corresponding lines in
        the results dataframe.
    """
    clf = LinearSVC_continuous(penalty='l2', fit_intercept=True)

    n_samples = train_size + 10000
    X, y = mk_data(n_samples=n_samples,
                   separability=sep, random_state=random_state,
                   noise_corr=noise_corr, dim=dim)
    X_train = X[:train_size]
    y_train = y[:train_size]
    X_test = X[train_size:]
    y_test = y[train_size:]

    validation_score = roc_auc_score(
                            y_test,
                            clf.fit(X_train, y_train).predict(X_test))

#    # Create 10 blocks of evenly-spaced labels for GroupShuffleSplit
    groups = np.arange(train_size) // (train_size // 10)
    
    scores = list()
    for name, cv in [('10 repeated 10-fold', 
                      RepeatedKFold(n_splits=10, n_repeats=10, 
                                              random_state=random_state)),
                     ('50 splits',
                      GroupShuffleSplit(n_splits=50, random_state=random_state))]:
        try:                 
            cv_scores = cross_val_score(clf, X_train, y_train, groups=groups, 
                                    scoring='roc_auc', cv=cv)
        except:
            if name == '10 repeated 10-fold':
                try:
                    cv_scores = [roc_auc_score(y_train, cross_val_predict(clf, X_train, y_train, groups=groups, cv=10))]
                except:
                    cv_scores = [np.nan]
            else:
                cv_scores = [np.nan]
                
            
        scores.append(dict(
            cv_name=name,
            validation_score=validation_score,
            train_size=train_size,
            dim=dim,
            noise_corr=noise_corr,
            sep=sep,
            score_error=(np.mean(cv_scores) - validation_score),
            score_sem=(np.std(cv_scores) / np.sqrt(len(cv_scores)))
            ))

    return scores



###############################################################################
# Make a figure

if __name__ == '__main__':
    from matplotlib import pyplot as plt
    # Do a simple plot
    X, y = mk_data(separability=.8, dim=2, noise_corr=0)
    plt.figure(figsize=(4.5, 4.5))
    ax = plt.axes([0.1, 0.1, .9, .9])
    plt.scatter(X[:, 0], X[:, 1], c=y, edgecolor='k',
                cmap=plt.cm.Paired, s=40)
    plt.axis('tight')
    ax.spines['right'].set_color('none')
    ax.spines['top'].set_color('none')
    plt.xticks(())
    plt.yticks(())
    plt.xlabel('X1', size=25)
    plt.ylabel('X2', size=25)
    plt.savefig('simulated_data.pdf',
                edgecolor='none', facecolor='none')



###############################################################################
# Run the simulations

N_JOBS = 16
N_DRAWS = 10000
mem = Memory(cachedir='cache')


results = pandas.DataFrame(
    columns=['cv_name', 'validation_score', 'train_size', 'dim',
             'noise_corr', 'sep', 'score_error', 'score_sem'])


for sep in (6.25, ):
 for train_size in (30, 100, 200, 250, 300, 1000):
    # Cap computing time
    n_draws = N_DRAWS if train_size < 500 else N_DRAWS // 10
    scores = Parallel(n_jobs=N_JOBS, verbose=10)(
                    delayed(mem.cache(sample_and_cross_val_clf))(
                            train_size=train_size,
                            noise_corr=0, dim=300, sep=sep,
                            random_state=i)
                    for i in range(n_draws))
    for line in scores:
        results = results.append(line)

results.to_csv('cross_validation_results_auc_{}_draws.csv'.format(N_DRAWS))


