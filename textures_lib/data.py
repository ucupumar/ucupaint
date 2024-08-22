import json 
from typing import Any

class SourceType:
	SOURCE_AMBIENTCG = "ambientcg"
	SOURCE_POLYHAVEN = "polyhaven"

class AssetItem:
	def __init__(self):
		self.id = ""
		self.name = ""
		self.thumbnail = ""
		self.source_type = ""

		self.attributes:dict[str, AssetAttribute] = {}

	def add_attribute(self, attribute:str, link:str, file_name:str, size:int) -> 'AssetAttribute':
		new_attribute = AssetAttribute()
		new_attribute.attribute = attribute
		new_attribute.asset = AssetDownload(link, file_name, size)

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
		self.asset:AssetDownload = None
		self.textures:list[AssetDownload] = [] # texture files for 

	def add_texture(self, texture:str, size:int) -> None:
		file_name:str = texture.split("/")[-1]
		self.textures.append(AssetDownload(texture, file_name, size))

	def to_dict(self) -> dict[str, Any]:
		return {
			"attribute": self.attribute,
			"asset": self.asset.to_dict() if self.asset else None,
			"textures": [t.to_dict() for t in self.textures]
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
	
class AssetDownload:
	def __init__(self, link:str, file_name:str, size:int):
		self.size = size
		self.link = link
		self.file_name = file_name

	def to_dict(self) -> dict[str, Any]:
		return {
			"size": self.size,
			"link": self.link,
			"file_name": self.file_name
		}
	
	@classmethod
	def from_dict(cls, data: dict[str, Any]) -> 'AssetDownload':
		instance = cls(data.get("link", ""), data.get("file_name", ""), data.get("size", 0))
		return instance
	
	def to_json(self) -> str:
		return json.dumps(self.to_dict())
	
	@classmethod
	def from_json(cls, json_str: str) -> 'AssetDownload':
		data = json.loads(json_str)
		return cls.from_dict(data)
	