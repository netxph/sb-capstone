import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

def plot_corr(corr):
    """Helper to create a correlation graph

    Args:
        corr (DataFrame): Correlation matrix

    Returns:
        None
    """

    mask = np.triu(np.ones_like(corr, dtype=bool))
    f, ax = plt.subplots(figsize=(16, 12))
    cmap = sns.diverging_palette(230, 20, as_cmap=True)

    sns.heatmap(corr, mask=mask, cmap=cmap, vmax=.3, center=0,
            square=True, linewidths=.5, cbar_kws={"shrink": .5});


def get_cv_results(cv):
    
    results = [[list(cv.cv_results_["params"][i].values()), cv.cv_results_["mean_test_score"][i]] for i in range(len(cv.cv_results_["params"]))]
    results = pd.DataFrame(results, columns=["params", "score"])

    return results