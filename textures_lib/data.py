import json 
from typing import Any

class SourceType:
	SOURCE_AMBIENTCG = "ambientcg"
	SOURCE_TEXTUREHAVEN = "texturehaven"

class AssetItem:
	def __init__(self):
		self.id = ""
		self.name = ""
		self.thumbnail = ""
		self.source_type = ""

		self.attributes:dict[str, AssetAttribute] = {}

	def add_attribute(self, attribute:str, link:str) -> 'AssetAttribute':
		new_attribute = AssetAttribute()
		new_attribute.attribute = attribute
		new_attribute.link = link

		self.attributes[attribute] = new_attribute
		return new_attribute

	def to_dict(self) -> dict[str, Any]:
		return {
			"id": self.id,
			"name": self.name,
			"thumbnail": self.thumbnail,
			"source_type": self.source_type,
			"attributes": {k: v.to_dict() for k, v in self.attributes.items()}
		}

	@classmethod
	def from_dict(cls, data: dict[str, Any]) -> 'AssetItem':
		instance = cls()
		instance.id = data.get("id", "")
		instance.name = data.get("name", "")
		instance.thumbnail = data.get("thumbnail", "")
		instance.attributes = {k: AssetAttribute.from_dict(v) for k, v in data.get("attributes", {}).items()}
		return instance

	def to_json(self) -> str:
		return json.dumps(self.to_dict())

	@classmethod
	def from_json(cls, json_str: str) -> 'AssetItem':
		data = json.loads(json_str)
		return cls.from_dict(data)
	
class AssetAttribute:
	def __init__(self):
		self.attribute = ""
		self.link = "" # zip file for ambientcg, blend file for texturehaven
		self.textures = [] # texture files for texturehaven

	def add_texture(self, texture:str):
		self.textures.append(texture)

	def to_dict(self) -> dict[str, Any]:
		return {
			"attribute": self.attribute,
			"link": self.link,
			"textures": self.textures
		}

	@classmethod
	def from_dict(cls, data: dict[str, Any]) -> 'AssetAttribute':
		instance = cls()
		instance.attribute = data.get("attribute", "")
		instance.link = data.get("link", "") 
		instance.textures = data.get("textures", [])
		return instance

	def to_json(self) -> str:
		return json.dumps(self.to_dict())

	@classmethod
	def from_json(cls, json_str: str) -> 'AssetAttribute':
		data = json.loads(json_str)
		return cls.from_dict(data)
	