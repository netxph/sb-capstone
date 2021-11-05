import pandas as pd
import numpy as np

OfferType = pd.CategoricalDtype(categories=['bogo', 'informational', 'discount', "no_offer"])
ChannelType = pd.CategoricalDtype(categories=['email', 'mobile', 'social', 'web'])

def clean_portfolio(portfolio):
    """Corrects types and values of columns

    Args:
        portfolio (pandas.DataFrame): DataFrame containing the portfolio data

    Returns:
        portfolio (pandas.DataFrame): DataFrame containing the cleaned portfolio data
    """

    portfolio.offer_type = portfolio.offer_type.astype(OfferType)
    portfolio.channels = portfolio.channels.apply(eval)

    return portfolio

GenderType = pd.CategoricalDtype(categories=['F', 'M', 'O', 'U'])

def clean_profile(profile):
    """Corrects types and values of columns

    Args:
        profile (pandas.DataFrame): DataFrame containing the profile data

    Returns:
        profile (pandas.DataFrame): DataFrame containing the cleaned profile data
    """

    profile.gender = profile.gender.astype(GenderType)    
    profile.became_member_on = pd.to_datetime(profile.became_member_on)

    return profile

EventType = pd.CategoricalDtype(categories=['offer_received', 'offer_viewed', 'offer_completed', 'transaction'], ordered=True)
OfferIDType = pd.CategoricalDtype(categories=[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10], ordered=True)

def clean_transcript(transcript):
    """Corrects types and values of columns

    Args:
        transcript (pandas.DataFrame): DataFrame containing the transcript data

    Returns:
        transcript (pandas.DataFrame): DataFrame containing the cleaned transcript data
    """

    transcript.event = transcript.event.astype(EventType)

    # offer_id does not make sense as numerical, let's convert it to categorical.
    transcript.offer_id = transcript.offer_id.astype(OfferIDType)

    return transcript

GenerationType = pd.CategoricalDtype(categories=["gen_z", "millenials", "gen_x", "boomers", "silent"], ordered=True)
AgeGroupType = pd.CategoricalDtype(categories=["young", "adult", "middle_age", "old"], ordered=True)

def clean_transcript_group(transcript_group):
    """Corrects types and values of columns

    Args:
        transcript_group (pandas.DataFrame): DataFrame containing the transcript group data

    Returns:
        transcript_group (pandas.DataFrame): DataFrame containing the cleaned transcript group data
    """

    transcript_group.mapped_offer = transcript_group.mapped_offer.astype(OfferIDType)
    transcript_group.offer_type = transcript_group.offer_type.astype(OfferType)
    transcript_group.gender = transcript_group.gender.astype(GenderType)
    transcript_group.generation = transcript_group.generation.astype(GenerationType)
    transcript_group.group = transcript_group.group.astype(AgeGroupType)

    return transcript_group

def tukey_rule(data, col):
    """Applies Tukey rule to a column of a DataFrame

    Args:
        data (pandas.DataFrame): DataFrame containing the data
        col (str): Name of the column to apply the rule to

    Returns:
        data (pandas.DataFrame): DataFrame containing the cleaned data
    """

    Q1 = data[col].quantile(0.25)
    Q3 = data[col].quantile(0.75)
    
    IQR = Q3 - Q1
    
    max_value = Q3 + (1.5 * IQR)
    min_value = Q1 - (1.5 * IQR)
    
    return data[(data[col] >= min_value) & (data[col] <= max_value)]