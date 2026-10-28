from datetime import datetime, timezone

from .database import get_db, get_fallback_store


def now():
    return datetime.now(timezone.utc)


def create_analysis(document):
    db = get_db()
    if db is None:
        get_fallback_store()["analyses"][document["analysis_id"]] = document.copy()
        return document
    db.analyses.insert_one(document)
    return document


def get_analysis(analysis_id):
    db = get_db()
    if db is not None:
        return db.analyses.find_one({"analysis_id": analysis_id})
    return get_fallback_store()["analyses"].get(analysis_id)


def update_analysis(analysis_id, values):
    db = get_db()
    if db is not None:
        db.analyses.update_one({"analysis_id": analysis_id}, {"$set": values})
    elif analysis_id in get_fallback_store()["analyses"]:
        get_fallback_store()["analyses"][analysis_id].update(values)


def list_analyses(query=None, skip=0, limit=20):
    db = get_db()
    if db is not None:
        return list(db.analyses.find(query or {}).sort("created_at", -1).skip(skip).limit(limit))
    values = list(get_fallback_store()["analyses"].values())
    if query and "analysis_name" in query:
        expression = query["analysis_name"].get("$regex", "").lower()
        values = [item for item in values if expression in item.get("analysis_name", "").lower()]
    return sorted(values, key=lambda item: item.get("created_at", now()), reverse=True)[skip:skip + limit]


def delete_analysis_records(analysis_id):
    db = get_db()
    if db is not None:
        db.analyses.delete_one({"analysis_id": analysis_id})
        db.images.delete_many({"analysis_id": analysis_id})
        db.crack_measurements.delete_many({"analysis_id": analysis_id})
        db.report_history.delete_many({"analysis_id": analysis_id})
    else:
        store = get_fallback_store()
        store["analyses"].pop(analysis_id, None)
        store["images"].pop(analysis_id, None)
        store["measurements"] = [item for item in store["measurements"] if item["analysis_id"] != analysis_id]
