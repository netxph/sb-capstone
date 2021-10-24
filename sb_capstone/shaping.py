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

def get_transcript_group(transcript):
    transcript_group = transcript \
        .sort_values(by=["person_id", "time", "event"]) \
        .groupby(["person_id", "offer_group"]) \
        .agg({
            "event": lambda x: x.tolist(), 
            "offer_id": "min", 
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

    mask = transcript_group.event.apply(lambda x: "transaction" in x)

    transcript_group.loc[(transcript_group.offer_type == "informational") & mask, "event"] = \
        transcript_group[(transcript_group.offer_type == "informational") & mask] \
            .event  \
            .apply(lambda x: [e if e != "transaction" else "offer_completed" for e in x])

    transcript_non_offer = transcript_group[transcript_group.offer_group < 0][["person_id", "wave", "amount"]].reset_index(drop=True).rename(columns={"amount": "non_offer_amount"})
    transcript_offer = transcript_group[transcript_group.offer_group > 0].reset_index(drop=True)

    transcript_group = transcript_offer.merge(transcript_non_offer, on=["person_id", "wave"], how="left")

    transcript_group.event = transcript_group.event.apply(lambda x: list(filter(lambda a: a != "transaction", x)))

    return transcript_group
