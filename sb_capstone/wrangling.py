import pandas as pd

OfferType = pd.CategoricalDtype(categories=['bogo', 'informational', 'discount'])
ChannelType = pd.CategoricalDtype(categories=['email', 'mobile', 'social', 'web'])

def clean_portfolio(portfolio):
    portfolio.offer_type = portfolio.offer_type.astype(OfferType)
    portfolio.channels = portfolio.channels.apply(eval)

    return portfolio

GenderType = pd.CategoricalDtype(categories=['F', 'M', 'O'])

def clean_profile(profile):
    profile.gender = profile.gender.astype(GenderType)    
    profile.became_member_on = pd.to_datetime(profile.became_member_on)

    return profile