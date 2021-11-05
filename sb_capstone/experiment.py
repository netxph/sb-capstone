import joblib
import numpy as np
import pandas as pd

from sklearn.model_selection import train_test_split
from sklearn.multioutput import MultiOutputClassifier
from sklearn.neighbors import KNeighborsClassifier
from sklearn.metrics import classification_report

from sb_capstone.shaping import (
    _simplify_gender,
    _transform_age_group,
    _transform_generation,
    _explode_membership_date,
    _extract_age_bins,
    _transform_gender
)

select_model = joblib.load("../models/select_offer.pkl")
receive_model = joblib.load("../models/receive_offer.pkl")

def train_receive_offer(data, file):
    """Trains data to create model to determine if a customer will receive an offer.

    Args:
        data (pandas.DataFrame): Data to train model on.
        file (str): File to save model to.

    Returns:
        str: File where the model is saved.
        dict: Classification report.
    """

    y = data.purchased
    X = data.drop(columns=["purchased"])

    X_train, X_test, y_train, y_test = train_test_split(X, y)

    clf = KNeighborsClassifier(n_neighbors=5, algorithm="kd_tree", leaf_size=10)
    clf.fit(X_train, y_train)

    y_pred = clf.predict(X_test)
    score = classification_report(y_test, y_pred, zero_division=True, output_dict=True)

    joblib.dump(clf, file)

    return file, score

def train_select_offer(data, file):
    """Trains data to create model to determine which offers to show to a customer.

    Args:
        data (pandas.DataFrame): Data to train model on.
        file (str): File to save model to.

    Returns:
        str: File where the model is saved.
        dict: Classification report.
    """

    y_cols = np.arange(1, 11).astype(str).tolist()

    y = data[y_cols]
    X = data[data.columns[~data.columns.isin(y_cols)]]

    X_train, X_test, y_train, y_test = train_test_split(X, y)

    clf = MultiOutputClassifier(
        KNeighborsClassifier(n_neighbors=5, algorithm="kd_tree", leaf_size=10)
    )

    clf.fit(X_train, y_train)

    y_pred = clf.predict(X_test)
    score = classification_report(y_test, y_pred, zero_division=True, output_dict=True)

    joblib.dump(clf, file)

    return file, score

def _convert_for_select(profile):
    """Convert profile to be fed into the select model.

    Args:
        profile (pandas.DataFrame): Profile to convert.

    Returns:
        pandas.DataFrame: Converted profile.
    """

    without_profile = profile[profile.age.isna()].reset_index(drop=True)
    profile = profile[~profile.age.isna()].reset_index(drop=True)

    profile = _simplify_gender(
        _explode_membership_date(profile))


    return profile, without_profile

def select_offer(profile, model = select_model, default_offers = []):
    """Predict which offers to show to a customer.

    Args:
        profile (pandas.DataFrame): Profile to predict offers for.
        model (sklearn.model_selection.Model): Model to use to predict offers.
        default_offers (list): Default offers to show to a customer who are anonymous.

    Returns:
        pandas.DataFrame: Profile with offers.
    """

    profile, without_profile = _convert_for_select(profile)
    
    offer_cols = np.arange(1, 11).astype(str).tolist()

    profile[offer_cols] = np.zeros(10, dtype=int).tolist()

    if len(profile) > 0:
        cols = [
            "gender",
            "age",
            "income", 
            "membership_year", 
            "membership_month", 
            "membership_day"
        ]


        y = pd.DataFrame(model.predict(profile[cols]), columns=offer_cols)

        profile[offer_cols] = y

    profile = profile[["id"] + offer_cols]
    profile = pd.melt(profile, id_vars="id", value_vars=np.arange(1, 11).astype(str).tolist(), var_name="recommended_offers")
    profile = profile[profile.value == 1]
    profile = profile.groupby("id").agg({"recommended_offers": lambda x: x.tolist()}).reset_index()

    without_profile["recommended_offers"] = [default_offers] * without_profile.shape[0] 
    without_profile = without_profile[["id", "recommended_offers"]]

    results = pd.concat([profile, without_profile])

    return results

def _convert_for_receive(profile):
    """Convert profile to be fed into the receive model.

    Args:
        profile (pandas.DataFrame): Profile to convert.

    Returns:
        pandas.DataFrame: Converted profile.
    """

    without_profile = profile[profile.age.isna()].reset_index(drop=True)
    profile = profile[~profile.age.isna()].reset_index(drop=True)
    
    profile = _transform_age_group(
        _transform_generation(
        _transform_gender(
        _explode_membership_date(
            _extract_age_bins(
            profile)))))
    
    return profile, without_profile

def receive_offer(profile, model = receive_model, default_value=pd.NA):
    """Predict whether the customer should receive an offer.

    Args:
        profile (pandas.DataFrame): Profile to predict offers for.
        model (sklearn.model_selection.Model): Model to use to predict offers.
        default_value (str): Default value to use if the customer is anonymous.

    Returns:
        pandas.DataFrame: Profile with offers.
    """

    profile, without_profile = _convert_for_receive(profile)

    profile["receive_offer"] = False

    cols = [
        "gender",
        "age",
        "income",
        "membership_year",
        "membership_month",
        "membership_day",
        "gen_z",
        "millenials",
        "gen_x",
        "boomers",
        "silent",
        "young",
        "adult",
        "middle_age",
        "old"
    ]

    if len(profile) > 0:
        y = model.predict(profile[cols])
        profile["receive_offer"] = y
        profile.receive_offer = profile.receive_offer.apply(lambda x: True if x==1.0 else False)
    
    profile = profile[["id", "receive_offer"]]

    without_profile["receive_offer"] = default_value
    without_profile = without_profile[["id", "receive_offer"]]

    results = pd.concat([profile, without_profile]).sort_values("id").reset_index(drop=True)

    return results
