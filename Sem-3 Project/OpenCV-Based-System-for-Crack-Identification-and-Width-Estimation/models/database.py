from pymongo import MongoClient


def init_db(app):
    app.extensions["fallback_store"] = {
        "analyses": {}, "images": {}, "measurements": [], "reports": []
    }
    try:
        client = MongoClient(app.config["MONGO_URI"], serverSelectionTimeoutMS=1500)
        db = client[app.config["MONGO_DB_NAME"]]
        db.command("ping")
        app.extensions["mongo_client"] = client
        app.extensions["mongo_db"] = db
        app.extensions["mongo_available"] = True
        # Clean up any legacy conflicting indexes from older project versions
        for coll, idx_name in [("analyses", "analysisId_1"), ("images", "storedFilename_1"), ("images", "imageHash_1")]:
            try:
                db[coll].drop_index(idx_name)
            except Exception:
                pass
        try:
            db.analyses.create_index("analysis_id", unique=True, sparse=True)
            db.images.create_index([("analysis_id", 1), ("uploaded_at", -1)])
            db.crack_measurements.create_index([("analysis_id", 1), ("image_id", 1)])
            db.report_history.create_index([("analysis_id", 1), ("generated_at", -1)])
        except Exception:
            pass
    except Exception:
        app.extensions["mongo_available"] = False
        app.extensions["mongo_db"] = None


def get_db():
    from flask import current_app
    return current_app.extensions.get("mongo_db")


def get_fallback_store():
    from flask import current_app
    return current_app.extensions["fallback_store"]
