import pandas as pd
import numpy as np
from sklearn.experimental import enable_iterative_imputer
from sklearn.impute import IterativeImputer

from sb_capstone.wrangling import (
    GenerationType,
    AgeGroupType,
    OfferIDType,
    OfferType,
    GenderType,
    tukey_rule
)

class OfferGroup():
    """Helper class to store offer groups

    Attributes:
        offer_id (int): The offer id
        offer_type (str): The offer type
        expires (int): The time the offer expires
        events (list): The events that have been added to the offer group
        difficulty (float): The difficulty of the offer group
        redeemed (bool): Whether the offer has been redeemed
        active (bool): Whether the offer is active
    """

    def __init__(self, row):
        """Initializes the class

        Args:
            row (pandas.Series): The row to initialize the class with
        """

        self.offer_id = row.offer_id
        self.offer_type = row.offer_type
        self.expires = (row.duration * 24) + row.time
        self.events = []
        self.difficulty = row.difficulty
        self.redeemed = False
        self.active = True

    def can_add_event(self, row):
        """Determines whether the offer group can add an event
        
        Args:
            row (pandas.Series): The row to check

        Returns:
            bool: Whether the offer group can add the event
        """

        if row.event != "transaction":
            return (row.offer_id == self.offer_id) and  \
                (not row.event in self.events)
        else:
            return (row.time <= self.expires) and (not self.redeemed) and (self.active)

    def add_event(self, row):
        """Adds an event to the offer group

        Args:
            row (pandas.Series): The row event to add

        Returns:
            None
        """

        if row.event != "transaction":
            self.events.append(row.event)
        else:
            self.difficulty = self.difficulty - row.amount
            self.redeemed = self.difficulty <= 0.0

    def deactivate(self):
        """Deactivates the offer group

        Args:
            None

        Returns:
            None
        """

        self.active = False

class OfferGroups():
    """Helper class to store offer groups
    """

    def __init__(self):
        """Initializes the class
        """

        self._groups = {}
        self._index = 0

    def get_group(self, row):
        """Returns the group that the row event belongs to

        Args:
            row (pandas.Series): The row event to add

        Returns:
            None
        """

        # there should have only one unique event per group
        result = -row.wave, 0

        for idx  in self._groups:
            group = self._groups[idx]
            if group.can_add_event(row):
                group.add_event(row)
                result = idx, group.offer_id
                break
        
        return result

    def add_group(self, row):
        """Adds a new group to the offer groups

        Args:
            row (pandas.Series): The row event to add

        Returns:
            None
        """

        # create a new group, initializing all variables

        for g in self._groups:
            self._groups[g].deactivate()

        self._index = self._index + 1
        self._groups[self._index] = OfferGroup(row)


def get_transcript_combined(transcript):
    """Gets an enriched transcript with new features

    Args:
        transcript(pandas.DataFrame): The transcript table to transform

    Returns:
        pandas.DataFrame: The enriched transcript
    """
    
    transcript["wave"] = pd.cut(transcript.time, bins=[-1, 167, 335, 407, 503, 575, 714], labels=np.arange(1,7))
    transcript["day"] = pd.cut(transcript.time, bins=np.arange(-1, 714 + 24, step=24), labels=np.arange(1, 30 + 1))

    transcript = transcript.rename(columns={"offer_id": "mapped_offer", "id": "offer_id"})

    transcript = transcript.groupby("person_id").apply(_get_offer_group)

    transcript.mapped_offer = transcript.mapped_offer.astype(OfferIDType)

    transcript = transcript.sort_values(by=["person_id", "time"])
    transcript["diffs"] = transcript.groupby("person_id").time.diff()
    transcript = transcript.sort_index()
    transcript.diffs = transcript.diffs.apply(lambda x: np.NaN if x == 0 else x)

    return transcript

def _get_offer_group(user_group):
    """Gets the offer group object

    Args:
        user_group (pandas.DataFrame): The user group to get the offer group for

    Returns:
        pandas.DataFrame: The enriched offer group
    """

    offer_groups = OfferGroups()

    for i, row in user_group.iterrows():
        if row.event == "offer_received":
            offer_groups.add_group(row)

        group_id, offer_id = offer_groups.get_group(row)

        user_group.loc[i, "offer_group"] = group_id
        user_group.loc[i, "offer_id"] = offer_id

    return user_group

def _mark_information_completed(transcript_group):
    """Marks whether the offer event is completed properly on informational offers

    Args:
        transcript_group (pandas.DataFrame): The transcript group to mark

    Returns:
        pandas.DataFrame: The modified transcript with updated informational event
    """

    mask = transcript_group.event.fillna("").apply(lambda x: "transaction" in x)

    transcript_group.loc[(transcript_group.offer_type == "informational") & mask, "event"] = \
        transcript_group[(transcript_group.offer_type == "informational") & mask] \
            .event  \
            .apply(lambda x: [e if e != "transaction" else "offer_completed" for e in x])

    return transcript_group

def _get_non_offer_amount(transcript_group):
    """Extracts the amount not related to offer

    Args:
        transcript_group (pandas.DataFrame): The transcript group to extract the amount from

    Returns:
        pandas.DataFrame: The modified transcript with the non-offer related amount
    """

    transcript_non_offer = transcript_group[transcript_group.offer_group < 0] \
        [["person_id", "wave", "amount"]]   \
            .reset_index(drop=True).rename(columns={"amount": "non_offer_amount"})

    transcript_offer = transcript_group[transcript_group.offer_group > 0] \
        .reset_index(drop=True)

    transcript_group = transcript_offer \
        .merge(transcript_non_offer, on=["person_id", "wave"], how="outer")

    transcript_group.event = transcript_group.event.apply(lambda x: [] if x is np.NaN else x)
    transcript_group.channels = transcript_group.channels.apply(lambda x: [] if x is np.NaN else x)

    return transcript_group

def _add_profiles_with_notrans(transcript_group, profile):
    """Attach customer profile to transcript

    Args:
        transcript_group (pandas.DataFrame): The transcript group to attach the profile to
        profile (pandas.DataFrame): The customer profile to attach

    Returns:
        pandas.DataFrame: The modified transcript with the profile attached
    """

    waves = []

    for i in transcript_group.wave.unique():
        wave = profile.copy()
        wave["wave"] = i
        waves.append(wave)

    profile_wave = pd.concat(waves)

    transcript_group = profile_wave \
        .merge( \
            transcript_group,  
            left_on=["id", "wave"], 
            right_on=["person_id", "wave"], 
            how="left")

    transcript_group.gender = transcript_group.gender.astype(GenderType)

    return transcript_group

def _promote_events_to_columns(transcript_group):
    """Promote the events values as columns

    Args:
        transcript_group (pandas.DataFrame): The transcript dataset

    Returns:
        pandas.DataFrame: The modified transcript with the events promoted as columns
    """

    transcript_group["received"] = transcript_group.event \
        .fillna("") \
        .apply(lambda x: x[0] == "offer_received" if len(x) > 0 else False)
    transcript_group["viewed"] = transcript_group.event \
        .fillna("") \
        .apply(lambda x: x[1] == "offer_viewed" if len(x) > 1 else False)
    transcript_group["completed"] = transcript_group.event \
        .fillna("") \
        .apply(lambda x: (x[2] == "offer_completed" or x[1] == "offer_completed") if len(x) > 2 else False)

    return transcript_group

def _promote_channels_to_columns(transcript_group):
    """Promote the channels values as columns

    Args:
        transcript_group (pandas.DataFrame): The transcript dataset

    Returns:
        pandas.DataFrame: The modified transcript with the channels promoted as columns
    """

    transcript_group \
        .loc[~transcript_group.channels.isna(), ["web", "email", "mobile", "social"]] =  \
            transcript_group \
                .loc[~transcript_group.channels.isna()] \
                .channels \
                .apply(lambda x: pd.Series([1] * len(x), index=x)) \
                .fillna(0, downcast='infer')

    return transcript_group

def _impute_missing_values(transcript_group):
    """Impute the missing values

    Args:
        transcript_group (pandas.DataFrame): The transcript dataset

    Returns:
        pandas.DataFrame: The modified transcript with the missing values imputed
    """

    transcript_group.amount = transcript_group.amount.fillna(0)
    transcript_group.reward = transcript_group.reward.fillna(0)
    transcript_group.non_offer_amount = transcript_group.non_offer_amount.fillna(0)
    transcript_group.mapped_offer = transcript_group.mapped_offer.fillna(0).astype(int)
    transcript_group.difficulty = transcript_group.difficulty.fillna(0)
    transcript_group.duration = transcript_group.duration.fillna(0)
    transcript_group.web = transcript_group.web.fillna(0).astype(bool)
    transcript_group.email = transcript_group.email.fillna(0).astype(bool)
    transcript_group.mobile = transcript_group.mobile.fillna(0).astype(bool)
    transcript_group.social = transcript_group.social.fillna(0).astype(bool)
    transcript_group.gender = transcript_group.gender.fillna("U")
    transcript_group.offer_type = transcript_group.offer_type.fillna("no_offer")

    diffs_mean = transcript_group.diffs.mean()
    transcript_group.diffs = transcript_group.diffs.fillna(diffs_mean)

    return transcript_group

def _remove_transaction_in_event(transcript_group):
    """Removes the transaction in the list of events

    Args:
        transcript_group (pandas.DataFrame): The transcript dataset

    Returns:
        pandas.DataFrame: The modified transcript with the transaction removed
    """

    transcript_group.event = transcript_group.event \
        .apply(lambda x: list(filter(lambda a: a != "transaction", x)) if x != np.NaN else [])

    return transcript_group

def _explode_membership_date(transcript_group):
    """Splits the membership date into year, month and day

    Args:
        transcript_group (pandas.DataFrame): The transcript dataset

    Returns:
        pandas.DataFrame: The modified transcript with the membership date exploded
    """

    transcript_group["membership_year"] = transcript_group.became_member_on.dt.year
    transcript_group["membership_month"] = transcript_group.became_member_on.dt.month
    transcript_group["membership_day"] = transcript_group.became_member_on.dt.day

    transcript_group = transcript_group.drop(columns=["became_member_on"])

    return transcript_group

def _extract_age_bins(transcript_group):
    """Extracts generation and age group from age

    Args:
        transcript_group (pandas.DataFrame): The transcript dataset

    Returns:
        pandas.DataFrame: The modified transcript with the age bins extracted
    """

    year = 2018

    transcript_group["generation"] = pd.cut( \
        transcript_group.age, \
        bins=[17, year-1997, year-1981, year-1965, year-1946, 101], \
        labels=["gen_z", "millenials", "gen_x", "boomers", "silent"] \
    )

    transcript_group.generation = transcript_group.generation.astype(GenerationType)

    transcript_group["group"] = pd.cut(transcript_group.age, bins=[17, 25, 40, 60, 101], labels=["young", "adult", "middle_age", "old"])
    transcript_group.group = transcript_group.group.astype(AgeGroupType)

    return transcript_group

def _extract_purchased(transcript_group):
    """Extracts the purchased column

    Args:
        transcript_group (pandas.DataFrame): The transcript dataset

    Returns:
        pandas.DataFrame: The modified transcript with the purchased column extracted
    """

    transcript_group.loc[~transcript_group.received, "purchased"] = transcript_group.non_offer_amount > 0.0
    transcript_group.loc[transcript_group.received, "purchased"] = transcript_group.viewed & transcript_group.completed

    return transcript_group

def _extract_offer_spendings(transcript_group):
    """Extracts the spendings per customer

    Args:
        transcript_group (pandas.DataFrame): The transcript dataset
    
    Returns:
        pandas.DataFrame: The modified transcript with the spendings per customer extracted
    """

    transcript_group["recommended_offer"] = transcript_group.apply(lambda x: 0 if x.purchased == False else x.mapped_offer, axis=1).astype(int)
    transcript_group["spendings"] = transcript_group.apply(lambda x: x.amount + x.non_offer_amount, axis=1)

    return transcript_group


def get_transcript_group(transcript, profile):
    """Flattens the transcript dataset and extracts features

    Args:
        transcript (pandas.DataFrame): The transcript dataset
        profile (pandas.DataFrame): The profile dataset

    Returns:
        pandas.DataFrame: The flattened transcript dataset
    """

    transcript_group = transcript \
        .sort_values(by=["person_id", "time", "event"]) \
        .groupby(["person_id", "offer_group"]) \
        .agg({
            "event": lambda x: x.tolist(), 
            "mapped_offer": "max", 
            "amount": "sum", 
            "reward": "max", 
            "offer_type": "first", 
            "channels": "first",
            "offer_reward": "max",
            "difficulty": "max",
            "duration": "max",
            "wave": "min",
            "diffs": "mean"
            }) \
        .reset_index()

    transcript_group.offer_type = transcript_group.offer_type.astype(OfferType)

    transcript_group = \
        _extract_offer_spendings(
            _impute_missing_values(
                _extract_purchased(
                    _extract_age_bins(
                        _promote_channels_to_columns(
                            _promote_events_to_columns(
                                _explode_membership_date(
                                    _add_profiles_with_notrans( \
                                        _remove_transaction_in_event( \
                                            _get_non_offer_amount( \
                                                _mark_information_completed(transcript_group))), profile))))))))


    
    transcript_group = transcript_group[[
        "id",
        "wave",
        "diffs",
        "received",
        "viewed", 
        "completed",
        "purchased",
        "amount",
        "reward",
        "non_offer_amount",
        "mapped_offer",
        "spendings",
        "recommended_offer",
        "offer_type",
        "difficulty",
        "duration",
        "web", 
        "email",
        "mobile",
        "social",
        "gender",
        "age",
        "generation",
        "group",
        "income",
        "membership_year",
        "membership_month",
        "membership_day"
    ]]

    return transcript_group

def _convert_gender(gender):
    """Helper method to transform gender

    Args:
        gender(str): The gender

    Returns:
        float: The converted value.
    """

    if gender == "M":
        return 1.0
    elif gender == "F":
        return 0.0
    else:
        return np.NaN

def _transform_bools(transcript_group):
    """Transform booleans to integers

    Args:
        transcript_group (pandas.DataFrame): The transcript dataset

    Returns:
        pandas.DataFrame: The modified transcript with the booleans transformed
    """

    transcript_group["received"] = transcript_group["received"].astype(int)
    transcript_group["viewed"] = transcript_group["viewed"].astype(int)
    transcript_group["completed"] = transcript_group["completed"].astype(int)
    transcript_group["purchased"] = transcript_group["purchased"].astype(int)
    transcript_group["web"] = transcript_group["web"].astype(int)
    transcript_group["email"] = transcript_group["email"].astype(int)
    transcript_group["mobile"] = transcript_group["mobile"].astype(int)
    transcript_group["social"] = transcript_group["social"].astype(int)

    return transcript_group

def _transform_offers(transcript_group):
    """Transform offers to dummies

    Args:
        transcript_group (pandas.DataFrame): The transcript dataset

    Returns:
        pandas.DataFrame: The modified transcript with the offers transformed
    """

    offer_dummies = pd.get_dummies(transcript_group.mapped_offer)
    offer_dummies.columns = offer_dummies.columns.astype(str)
    transcript_group = transcript_group.drop(columns=["mapped_offer"])

    transcript_group = pd.concat([transcript_group, offer_dummies], axis=1)

    return transcript_group

def _transform_offer_types(transcript_group):
    """Transform offer types to dummies

    Args:
        transcript_group (pandas.DataFrame): The transcript dataset

    Returns:
        pandas.DataFrame: The modified transcript with the offer types transformed
    """

    offer_type_dummies = pd.get_dummies(transcript_group.offer_type)
    transcript_group = transcript_group.drop(columns=["offer_type"])

    transcript_group = pd.concat([transcript_group, offer_type_dummies], axis=1)

    return transcript_group

def _transform_gender(transcript_group):
    """Transform gender for model training

    Args:
        transcript_group (pandas.DataFrame): The transcript dataset

    Returns:
        pandas.DataFrame: The modified transcript with the gender transformed
    """

    transcript_group.gender = transcript_group.gender.apply(_convert_gender)

    return transcript_group

def _transform_generation(transcript_group):
    """Transform generation to dummies

    Args:
        transcript_group (pandas.DataFrame): The transcript dataset

    Returns:
        pandas.DataFrame: The modified transcript with the generation transformed
    """

    gen_dummies = pd.get_dummies(transcript_group.generation)
    transcript_group = transcript_group.drop(columns=["generation"])

    transcript_group = pd.concat([transcript_group, gen_dummies], axis=1)

    return transcript_group

def _transform_age_group(transcript_group):
    """Transform age group to dummies

    Args:
        transcript_group (pandas.DataFrame): The transcript dataset

    Returns:
        pandas.DataFrame: The modified transcript with the age group transformed
    """

    group_dummies = pd.get_dummies(transcript_group.group)
    transcript_group = transcript_group.drop(columns=["group"])

    transcript_group = pd.concat([transcript_group, group_dummies], axis=1)

    return transcript_group

def _select_fields_for_receive(transcript_group):
    """Selects only the fields for receive model training

    Args:
        transcript_group (pandas.DataFrame): The transcript dataset

    Returns:
        pandas.DataFrame: The modified transcript with the fields for receive model training
    """

    cols = [
        "purchased",
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

    transcript_group = transcript_group[cols]

    return transcript_group

def _filter_for_receive(transcript_group):
    """Remove the data that we are not going to use.

    Args:
        transcript_group (pandas.DataFrame): The transcript dataset

    Returns:
        pandas.DataFrame: The modified transcript with rows filtered
    """

    transcript_group = transcript_group[~transcript_group.age.isna() & transcript_group.received]

    return transcript_group

def _impute_missing(transcript_group):
    """Impute missing values

    Args:
        transcript_group (pandas.DataFrame): The transcript dataset

    Returns:
        pandas.DataFrame: The modified transcript with missing imputed.
    """

    imputer = IterativeImputer(initial_strategy="most_frequent")
    transcript_group = pd.DataFrame(imputer.fit_transform(transcript_group), columns=transcript_group.columns)

    return transcript_group

def convert_for_receive_training(transcript_group):
    """Convert the transcript dataset for the receive model training

    Args:
        transcript_group (pandas.DataFrame): The transcript dataset

    Returns:
        pandas.DataFrame: The modified transcript with the features for receive model training
    """

    return _impute_missing(
        _select_fields_for_receive(
            _filter_for_receive(
                _transform_age_group(
                    _transform_generation(
                        _transform_gender(
                            _transform_offer_types(
                                _transform_offers(
                                    _transform_bools(transcript_group)))))))))

def get_transcript_offers(transcript_group):
    """Flatten the transcript further to get only the successful offers.

    Args:
        transcript_group (pandas.DataFrame): The transcript dataset
    
    Returns:
        pandas.DataFrame: The modified transcript with the offers flattened
    """

    transcript_group = transcript_group[transcript_group.recommended_offer != 0].groupby("id").agg({
        "recommended_offer": lambda x: list(dict.fromkeys(x.tolist())),
        "gender": "first",
        "age": "max",
        "income": "max",
        "membership_year": "max",
        "membership_month": "max",
        "membership_day": "max"
    }).reset_index()

    return transcript_group

def _dummify_recommended_offer(transcript_group):
    """Convert recommended offer to dummies

    Args:
        transcript_group (pandas.DataFrame): The transcript dataset

    Returns:
        pandas.DataFrame: The modified transcript with the recommended offer transformed
    """

    offers = pd.get_dummies(transcript_group.recommended_offer.explode()).groupby(level=0).sum()
    offers.columns = offers.columns.astype(str)

    transcript_group = pd.concat([transcript_group, offers], axis=1).drop(columns="recommended_offer")

    return transcript_group

def _simplify_gender(transcript_group):
    """Simplify gender column for training

    Args:
        transcript_group (pandas.DataFrame): The transcript dataset

    Returns:
        pandas.DataFrame: The modified transcript with gender data simplified.
    """

    transcript_group = transcript_group[transcript_group.gender != "O"].reset_index()
    transcript_group.gender = transcript_group.gender.apply(lambda x: 1 if x == "M" else 0)
    transcript_group = transcript_group.drop(columns=["index"])

    return transcript_group

def _filter_for_select(transcript_group):
    """Filter the records that we'll be using for the select model training

    Args:
        transcript_group (pandas.DataFrame): The transcript dataset

    Returns:
        pandas.DataFrame: The modified transcript with the records filtered
    """

    transcript_group = transcript_group[~transcript_group.age.isna()]
    transcript_group = tukey_rule(transcript_group, "income")

    return transcript_group

def _select_fields_for_select(transcript_group):
    """Select the fields for the select model training

    Args:
        transcript_group (pandas.DataFrame): The transcript dataset

    Returns:
        pandas.DataFrame: The modified transcript with the fields for select model training
    """

    transcript_group = transcript_group.drop(columns=["id"])
    return transcript_group

def convert_for_select_training(transcript_group):
    """Convert data for the select model training

    Args:
        transcript_group (pandas.DataFrame): The transcript dataset

    Returns:
        pandas.DataFrame: The modified transcript with the features for select model training
    """

    return _select_fields_for_select(
        _dummify_recommended_offer(
            _simplify_gender(
                _filter_for_select(
                    get_transcript_offers(transcript_group)))))