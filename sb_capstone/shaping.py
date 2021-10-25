import pandas as pd
import numpy as np

class OfferGroup():

    def __init__(self, row):
        self.offer_id = row.offer_id
        self.offer_type = row.offer_type
        self.expires = (row.duration * 24) + row.time
        self.events = []
        self.difficulty = row.difficulty
        self.redeemed = False
        self.active = True

    def can_add_event(self, row):
        if row.event != "transaction":
            return (row.offer_id == self.offer_id) and  \
                (not row.event in self.events)
        else:
            return (row.time <= self.expires) and (not self.redeemed) and (self.active)

    def add_event(self, row):
        if row.event != "transaction":
            self.events.append(row.event)
        else:
            self.difficulty = self.difficulty - row.amount
            self.redeemed = self.difficulty <= 0.0

    def deactivate(self):
        self.active = False

class OfferGroups():

    def __init__(self):
        self._groups = {}
        self._index = 0

    def get_group(self, row):
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
        # create a new group, initializing all variables

        for g in self._groups:
            self._groups[g].deactivate()

        self._index = self._index + 1
        self._groups[self._index] = OfferGroup(row)


def get_transcript_combined(transcript):
    transcript["wave"] = pd.cut(transcript.time, bins=[-1, 167, 335, 407, 503, 575, 714], labels=np.arange(1,7))
    transcript["day"] = pd.cut(transcript.time, bins=np.arange(-1, 714 + 24, step=24), labels=np.arange(1, 30 + 1))

    transcript = transcript.rename(columns={"offer_id": "mapped_offer", "id": "offer_id"})

    return transcript.groupby("person_id").apply(_get_offer_group)

def _get_offer_group(user_group):
    offer_groups = OfferGroups()

    for i, row in user_group.iterrows():
        if row.event == "offer_received":
            offer_groups.add_group(row)

        group_id, offer_id = offer_groups.get_group(row)

        user_group.loc[i, "offer_group"] = group_id
        user_group.loc[i, "offer_id"] = offer_id

    return user_group

def _mark_information_completed(transcript_group):
    mask = transcript_group.event.fillna("").apply(lambda x: "transaction" in x)

    transcript_group.loc[(transcript_group.offer_type == "informational") & mask, "event"] = \
        transcript_group[(transcript_group.offer_type == "informational") & mask] \
            .event  \
            .apply(lambda x: [e if e != "transaction" else "offer_completed" for e in x])

    return transcript_group

def _get_non_offer_amount(transcript_group):
    transcript_non_offer = transcript_group[transcript_group.offer_group < 0] \
        [["person_id", "wave", "amount"]]   \
            .reset_index(drop=True).rename(columns={"amount": "non_offer_amount"})

    transcript_offer = transcript_group[transcript_group.offer_group > 0] \
        .reset_index(drop=True)

    transcript_group = transcript_offer \
        .merge(transcript_non_offer, on=["person_id", "wave"], how="left")

    return transcript_group

def _add_profiles_with_notrans(transcript_group, profile):
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

    return transcript_group

def _promote_events_to_columns(transcript_group):
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
    transcript_group \
        .loc[~transcript_group.channels.isna(), ["web", "email", "mobile", "social"]] =  \
            transcript_group \
                .loc[~transcript_group.channels.isna()] \
                .channels \
                .apply(lambda x: pd.Series([1] * len(x), index=x)) \
                .fillna(0, downcast='infer')

    return transcript_group

def _impute_missing_values(transcript_group):
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

    return transcript_group

def _remove_transaction_in_event(transcript_group):

    transcript_group.event = transcript_group.event \
        .apply(lambda x: list(filter(lambda a: a != "transaction", x)))

    return transcript_group

def get_transcript_group(transcript, profile):
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
            "wave": "min"
            }) \
        .reset_index()

    transcript_group = \
        _impute_missing_values(
            _promote_channels_to_columns(
                _promote_events_to_columns(
                    _add_profiles_with_notrans( \
                        _remove_transaction_in_event( \
                            _get_non_offer_amount( \
                                _mark_information_completed(transcript_group))), profile))))

    
    transcript_group = transcript_group[[
        "id",
        "wave",
        "received",
        "viewed", 
        "completed",
        "amount",
        "reward",
        "non_offer_amount",
        "mapped_offer",
        "offer_type",
        "difficulty",
        "duration",
        "web", 
        "email",
        "mobile",
        "social",
        "gender",
        "age",
        "income",
        "became_member_on"
    ]]

    return transcript_group
