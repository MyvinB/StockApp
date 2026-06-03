import os
from dataclasses import dataclass
from dotenv import load_dotenv


@dataclass(frozen=True)
class GrowwConfig:
    api_key: str
    api_secret: str

    @classmethod
    def from_env(cls) -> "GrowwConfig":
        load_dotenv()
        return cls(
            api_key=os.environ["GROWW_API_KEY"],
            api_secret=os.environ["GROWW_API_SECRET"],
        )
