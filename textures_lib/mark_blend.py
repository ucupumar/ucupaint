import sys, bpy, os

argv = sys.argv
argv = argv[argv.index("--") + 1 :]  # get all args after "--"

arg_dict = {}

for i, content in enumerate(argv):
	print(i, " >> ",argv[i])


# parse arguments
for i in range(0, len(argv), 2):
	key = argv[i]
	key = key.replace("--", "")

	arg_dict[key] = argv[i + 1]

print(arg_dict)

id = arg_dict["id"]
cat_id = arg_dict["category_id"]

# file path
blend_file = bpy.data.filepath
blend_dir = os.path.dirname(blend_file)
os.chdir(blend_dir)

try:
	asset = bpy.data.materials[id]
except KeyError as e:
	if len(bpy.data.materials) == 1:
		asset = bpy.data.materials[0]
	else:
		raise e

asset.name = id + "_" + arg_dict["attribute"]	
asset.asset_mark()

if cat_id:
    asset.asset_data.catalog_id = cat_id

tags = arg_dict["tags"].split(";")

if tags:
	for t in tags:
		asset.asset_data.tags.new(t, skip_if_exists=True)
asset.asset_data.description = "Material by polyhaven.com"

override = bpy.context.copy()
override["id"] = asset

thumbnail_file = os.path.join(blend_dir, arg_dict["id"]+".png")
print("thumbfile: ", thumbnail_file)

with bpy.context.temp_override(**override):
    bpy.ops.ed.lib_id_load_custom_preview(filepath=thumbnail_file)

bpy.context.preferences.filepaths.save_version = 0  # Avoid .blend1
bpy.ops.wm.save_mainfile(relative_remap=True)
