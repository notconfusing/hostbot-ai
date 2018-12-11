# example taken from http://pythoncentral.io/introductory-tutorial-python-sqlalchemy/
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, BigInteger, Index, Float
from sqlalchemy.dialects.mysql import TINYTEXT, MEDIUMTEXT, LONGTEXT, JSON
from sqlalchemy.ext.declarative import declarative_base
import datetime

Base = declarative_base()

class candidates(Base):
    __tablename__ = 'candidates'
    __table_args__ = {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8', 'mysql_collate': 'utf8_general_ci'}
    user_id                    = Column(Integer, primary_key = True)
    user_name                  = Column(MEDIUMTEXT)
    user_registration          = Column(DateTime, index=True)
    user_editcount             = Column(Integer)
    candidate_status           = Column(TINYTEXT, default='unpredicted') # see utils/common.py
    invite_sent                = Column(TINYTEXT, default=None)
    created_at                 = Column(DateTime, index=True, default=datetime.datetime.utcnow)

class predictions(Base):
    __tablename__ = 'predictions'
    user_id                 = Column(Integer, primary_key = True)
    predicted_at            = Column(DateTime, index=True, default=datetime.datetime.utcnow)
    user_summary            = Column(JSON)
    pred_min                = Column(Float)
    pred_mean               = Column(Float)
    pred_error              = Column(JSON)
