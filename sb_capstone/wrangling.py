import pandas as pd
import numpy as np

OfferType = pd.CategoricalDtype(categories=['bogo', 'informational', 'discount', "no_offer"])
ChannelType = pd.CategoricalDtype(categories=['email', 'mobile', 'social', 'web'])

def clean_portfolio(portfolio):
    portfolio.offer_type = portfolio.offer_type.astype(OfferType)
    portfolio.channels = portfolio.channels.apply(eval)

    return portfolio

GenderType = pd.CategoricalDtype(categories=['F', 'M', 'O', 'U'])

def clean_profile(profile):
    profile.gender = profile.gender.astype(GenderType)    
    profile.became_member_on = pd.to_datetime(profile.became_member_on)

    return profile

EventType = pd.CategoricalDtype(categories=['offer_received', 'offer_viewed', 'offer_completed', 'transaction'], ordered=True)
OfferIDType = pd.CategoricalDtype(categories=[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10])


def clean_transcript(transcript):
    transcript.event = transcript.event.astype(EventType)

    # offer_id does not make sense as numerical, let's convert it to categorical.
    transcript.offer_id = transcript.offer_id.astype(OfferIDType)

    return transcript

def s3_remove_outliers(data):
    # 3 sigma technique

    outliers = {}
    for col in data.columns:
        if (str(data[col].dtype) != 'object') and (str(data[col].dtype) != 'category'):
            data = data[np.abs(data[col] - data[col].mean()) < (3 * data[col].std())]
            olrs = data[~(np.abs(data[col] - data[col].mean()) < (3 * data[col].std()))]
            outliers = pd.DataFrame(olrs)

    return data, outliers

def tukey_rule(data, col):
    Q1 = data[col].quantile(0.25)
    Q3 = data[col].quantile(0.75)
    
    IQR = Q3 - Q1
    
    max_value = Q3 + (1.5 * IQR)
    min_value = Q1 - (1.5 * IQR)
    
    return data[(data[col] >= min_value) & (data[col] <= max_value)]