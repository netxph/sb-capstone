class OfferGroup():

    def __init__(self, row):
        self.offer_id = row.offer_id
        self.offer_type = row.offer_type
        self.expires = (row.duration * 24) + row.time
        self.events = []
        self.difficulty = row.difficulty
        self.redeemed = False

    def can_add_event(self, row):
        if row.event != "transaction":
            return (row.offer_id == self.offer_id) and  \
                (not row.event in self.events) and \
                    (row.time <= self.expires)
        else:
            return (row.time <= self.expires) and (not self.redeemed)

    def add_event(self, row):
        if row.event != "transaction":
            self.events.append(row.event)
        else:
            self.difficulty = self.difficulty - row.amount
            self.redeemed = self.difficulty <= 0.0

class OfferGroups():

    def __init__(self):
        self._groups = {}
        self._index = 0

    def get_group(self, row):
        # there should have only one unique event per group
        result = 0, 0

        for idx  in self._groups:
            group = self._groups[idx]
            if group.can_add_event(row):
                group.add_event(row)
                result = idx, group.offer_id
                break
        
        return result

    def add_group(self, row):
        # create a new group, initializing all variables
        self._index = self._index + 1
        self._groups[self._index] = OfferGroup(row)


def get_transcript_group(transcript):
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