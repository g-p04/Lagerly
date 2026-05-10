from enum import Enum

class FormatTyp(str, Enum):
    pdf = "pdf"
    jpg = "jpg"
    png = "png"

class Status(str, Enum):
    pending = "pending"
    review = "review"
    approved = "approved"
    rejected = "rejected"

class Einheit(str, Enum):
    kg = "kg"
    g = "g"
    l = "l"
    ml = "ml"
    liter = "liter"
    stueck = "stueck"
    stk = "stk"
    pack = "pack"
    karton = "karton"