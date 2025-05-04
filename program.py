from typing import Annotated
import uvicorn
from fastapi import FastAPI, Depends
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, String, Integer
from sqlalchemy.orm import sessionmaker, Mapped, mapped_column, DeclarativeBase
from sqlalchemy.dialects.postgresql import JSON
from fastapi.middleware.cors import CORSMiddleware

engine = create_engine(f"postgresql://postgres:yGuuSpkqSTpQrtfZOhAiZfVSRBxzMexc@postgres.railway.internal:5432/railway")

class Base(DeclarativeBase): pass

Session = sessionmaker(bind=engine)

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String, unique=True)
    url: Mapped[str] = mapped_column(String, unique=True)
    cards: Mapped[list[str]] = mapped_column(JSON, default=list)
    unfilled: Mapped[int] = mapped_column(Integer, default=0)

    def set_username(self, username: str):
        self.username = username
        return self

    def set_youtube_url(self, youtube: str):
        self.url = youtube
        return self

Base.metadata.create_all(bind=engine)

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Replace "*" with your domain for better security
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
class UserModel(BaseModel):
    username: str
    url: str

def get_db():
    session = Session()
    try:
        yield session
    finally:
        session.close()

db_dependency = Annotated[Session, Depends(get_db)]

@app.post("/setup-user/{username}")
def setup_user(username: str, db: db_dependency):
    all_users = db.query(User).all()
    urls = [u.url for u in all_users if u.username != username]
    user = db.query(User).filter_by(username=username).first()
    if user:
        user.cards = urls
        db.commit()
        db.refresh(user)
    return {"status": "ok"}

@app.post("/add-user")
def add_user(model: UserModel, db: db_dependency):
    user = db.query(User).filter_by(username=model.username).first()
    if user:
        return {"detail": "User already exists"}
    user = User().set_username(model.username).set_youtube_url(model.url)
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"status": "created", "user_id": user.id}

@app.get("/get-users")
def get_users(db: db_dependency):
    return db.query(User).all()

@app.post("/{user1}-subscribed-to-{user2}")
def somebody_subscribed_to_somebody(user1: str, user2: str, db: db_dependency):
    db_user1 = db.query(User).filter_by(username=user1).first()
    db_user2 = db.query(User).filter_by(url=user2).first()
    if not db_user1 or not db_user2:
        return {"error": "user not found"}
    db_user1.unfilled += 1
    db_user2.unfilled = max(db_user2.unfilled - 1, 0)

    for user in db.query(User).all():
        if user.url != db_user1.url:
            user.cards = [db_user1.url] + user.cards

    db.commit()
    return {"status": "updated"}

@app.post("/{username}/update-cards")
def update_cards(db: db_dependency, username: str):
    user = db.query(User).filter_by(username=username).first()
    user.cards = user.cards[1:] + user.cards[0]
    db.commit()
    db.refresh(user)

if __name__ == "__main__":
    uvicorn.run(app, port=8081)
