from typing import List

from fastapi import Depends, FastAPI, HTTPException, Response, File
from sqlalchemy.orm import Session

from easydiffusion import bucket_crud, bucket_models, bucket_schemas
from easydiffusion.bucket_database import SessionLocal, engine

from requests.compat import urlparse

import base64, json

MIME_TYPES = {
    "jpg":  "image/jpeg",
    "jpeg": "image/jpeg",
    "gif":  "image/gif",
    "png":  "image/png",
    "webp": "image/webp",
    "js":   "text/javascript",
    "htm":  "text/html",
    "html": "text/html",
    "css":  "text/css",
    "json": "application/json",
    "mjs":  "application/json",
    "yaml": "application/yaml",
    "svg":  "image/svg+xml",
    "txt":  "text/plain",
}

def init():
    from easydiffusion.server import server_api

    bucket_models.BucketBase.metadata.create_all(bind=engine)


    # Dependency
    def get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    @server_api.get("/bucket/{obj_path:path}")
    def bucket_get_object(obj_path: str, db: Session = Depends(get_db)):
        filename = get_filename_from_url(obj_path)
        path = get_path_from_url(obj_path)

        if filename==None:
            bucket = bucket_crud.get_bucket_by_path(db, path=path)
            if bucket == None:
                raise HTTPException(status_code=404, detail="Bucket not found")
            bucketfiles = db.query(bucket_models.BucketFile).with_entities(bucket_models.BucketFile.filename).filter(bucket_models.BucketFile.bucket_id == bucket.id).all()
            bucketfiles = [ x.filename for x in bucketfiles ]
            return bucketfiles

        else:
            bucket_id = bucket_crud.get_bucket_by_path(db, path).id
            bucketfile = db.query(bucket_models.BucketFile).filter(bucket_models.BucketFile.bucket_id == bucket_id, bucket_models.BucketFile.filename == filename).first()

            suffix = get_suffix_from_filename(filename)

            return Response(content=bucketfile.data, media_type=MIME_TYPES.get(suffix, "application/octet-stream")) 

    @server_api.post("/bucket/{obj_path:path}")
    def bucket_post_object(obj_path: str, file: bytes = File(), db: Session = Depends(get_db)):
        filename = get_filename_from_url(obj_path)
        path = get_path_from_url(obj_path)
        bucket = bucket_crud.get_bucket_by_path(db, path)

        if bucket == None:
            bucket_id = bucket_crud.create_bucket(db=db, bucket=bucket_schemas.BucketCreate(path=path))
        else:
            bucket_id = bucket.id

        bucketfile = bucket_schemas.BucketFileCreate(filename=filename, data=file)
        result = bucket_crud.create_bucketfile(db=db, bucketfile=bucketfile, bucket_id=bucket_id)
        result.data = base64.encodestring(result.data)
        return result

    @server_api.post("/buckets/", response_model=bucket_schemas.Bucket)
    def create_bucket(bucket: bucket_schemas.BucketCreate, db: Session = Depends(get_db)):
        db_bucket = bucket_crud.get_bucket_by_path(db, path=bucket.path)
        if db_bucket:
            raise HTTPException(status_code=400, detail="Bucket already exists")
        return bucket_crud.create_bucket(db=db, bucket=bucket)

    @server_api.get("/buckets/", response_model=List[bucket_schemas.Bucket])
    def read_bucket(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
        buckets = bucket_crud.get_buckets(db, skip=skip, limit=limit)
        return buckets


    @server_api.get("/buckets/{bucket_id}", response_model=bucket_schemas.Bucket)
    def read_bucket(bucket_id: int, db: Session = Depends(get_db)):
        db_bucket = bucket_crud.get_bucket(db, bucket_id=bucket_id)
        if db_bucket is None:
            raise HTTPException(status_code=404, detail="Bucket not found")
        return db_bucket


    @server_api.post("/buckets/{bucket_id}/items/", response_model=bucket_schemas.BucketFile)
    def create_bucketfile_in_bucket(
        bucket_id: int, bucketfile: bucket_schemas.BucketFileCreate, db: Session = Depends(get_db)
    ):
        bucketfile.data = base64.decodestring(bucketfile.data)
        result =  bucket_crud.create_bucketfile(db=db, bucketfile=bucketfile, bucket_id=bucket_id)
        result.data = base64.encodestring(result.data)
        return result


    @server_api.get("/bucketfiles/", response_model=List[bucket_schemas.BucketFile])
    def read_bucketfiles(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
        bucketfiles = bucket_crud.get_bucketfiles(db, skip=skip, limit=limit)
        return bucketfiles


def get_filename_from_url(url):
    path = urlparse(url).path
    name = path[path.rfind('/')+1:]
    return name or None 

def get_path_from_url(url):
    path = urlparse(url).path
    path = path[0:path.rfind('/')]
    return path or None 

def get_suffix_from_filename(filename):
    return filename[filename.rfind('.')+1:]
