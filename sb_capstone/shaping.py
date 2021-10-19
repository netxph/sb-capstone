def get_transcript_group(transcript):
    return transcript.groupby("person_id").apply(_get_offer_group)

def _get_offer_group(user_group):
    offer_groups = {}
    offer_idx = 0

    for i, row in user_group.iterrows():
        if row.event == "offer_received":
            offer_idx = offer_idx + 1
            group_id = f"{offer_idx}:{row.offer_id}"

            offer_groups[group_id] = [row.event]
            user_group.loc[i, "offer_group"] = offer_idx

        elif row.event in ["offer_viewed", "offer_completed"]:
            idx, group_id = _find_offer_index(offer_groups, row.event, row.offer_id)

            offer_groups[group_id].append(row.event)
            user_group.loc[i, "offer_group"] = idx
        else:
            user_group.loc[i, "offer_group"] = 0

    return user_group

def _find_offer_index(offer_groups, event, offer_id):
    for group_id in offer_groups:
        idx, id = group_id.split(":")

        if (int(id) == offer_id) and (event not in offer_groups[group_id]):
            return int(idx), group_id

    return 0, None

def get_transcript_sequence(transcript_group):
    transcript_seq = transcript_group[transcript_group.event != "transaction"] \
        .groupby(["person_id","offer_group"]) \
        .agg({"event": lambda x: x.tolist(), "offer_id": lambda x: x.iloc[0]}) \
        .reset_index()
    
    transcript_seq["offer_success"] = transcript_seq.event.apply(_map_event_to_desc)
    transcript_seq["completed"] = transcript_seq.event.apply(lambda x: "offer_completed" in x)
    transcript_seq["success"] = transcript_seq.offer_success.apply(lambda x: x == "success")

    return transcript_seq

def _map_event_to_desc(event_seq):
    seq = ",".join(event_seq)

    if seq == "offer_received,offer_viewed,offer_completed":
        return "success"
    elif seq == "offer_received,offer_viewed":
        return "failed_viewed"
    elif (seq == "offer_received,offer_completed") or (seq == "offer_received,offer_completed,offer_viewed"):
        return "success_without_offer"
    elif seq == "offer_received":
        return "failed"
    else:
        return None

def get_transcript_active(transcript_portfolio):
    transcript_active = transcript_portfolio.groupby("person_id").apply(_get_active_offers)
    transcript_active.active_offers = transcript_active.active_offers.apply(lambda x: x if len(x) > 0 else None)

    return transcript_active

def _get_active_offers(user_portfolio_group):
    user_portfolio_group["active_offers"] = None
    index = 0
    offers = {}

    for i, row in user_portfolio_group.iterrows():
        if row.event == "offer_received":
            offers[index] = (row.offer_id, row.time + (row.duration * 24))
            index = index + 1

        for j in list(offers.keys()):
            if row.time > offers[j][1]:
                del offers[j]

        user_portfolio_group.at[i, "active_offers"] = [o[0] for o in list(offers.values())]

    return user_portfolio_group

