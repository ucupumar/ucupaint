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


dir_target = arg_dict["target"] #os.path.join(arg_dict["target"], arg_dict["id"]) 
# dir_source = arg_dict["source"]
tags = arg_dict["tags"].split(";")

# check dir exist or make dir
if not os.path.exists(dir_target):
	os.makedirs(dir_target)

cat_id = arg_dict["category_id"]

# create blend file
bpy.ops.wm.read_factory_settings(use_empty=True)


# save to blend file
target_path = os.path.join(dir_target, arg_dict["id"]+".blend")
print("target path: ", target_path)
bpy.ops.wm.save_as_mainfile(filepath=target_path)


# Load image textures and create materials
image_paths = []
for f in os.listdir(dir_target):
	if f.endswith(".blend"):
		continue
	image_paths.append(f)
print("image paths: ", image_paths)

# materials = []

# print current directory
print("current directory: ", os.getcwd())
# change active directory
os.chdir(dir_target)
print("current directory next: ", os.getcwd())

new_material = bpy.data.materials.new(name=arg_dict["id"]+"_"+arg_dict["attribute"])
# Create material
new_material.use_nodes = True
bsdf = new_material.node_tree.nodes["Principled BSDF"]


for image_path in image_paths:

	print("load image: ", image_path)	
	# Load image
	image = bpy.data.images.load("//"+image_path)

	# Create texture
	base_name = os.path.basename(image_path)

	texture = bpy.data.textures.new(name=base_name, type='IMAGE')
	texture.image = image

	check_name = base_name.lower()
	if "color" in check_name:
		tex_image = new_material.node_tree.nodes.new('ShaderNodeTexImage')
		tex_image.image = image
		new_material.node_tree.links.new(bsdf.inputs['Base Color'], tex_image.outputs['Color'])
	elif "normal" in check_name:
		tex_image = new_material.node_tree.nodes.new('ShaderNodeTexImage')
		tex_image.image = image
		new_material.node_tree.links.new(bsdf.inputs['Normal'], tex_image.outputs['Color'])
	elif "roughness" in check_name:
		tex_image = new_material.node_tree.nodes.new('ShaderNodeTexImage')
		tex_image.image = image
		new_material.node_tree.links.new(bsdf.inputs['Roughness'], tex_image.outputs['Color'])

thumbnail_file = os.path.join(dir_target, arg_dict["id"]+".png")
new_material.asset_mark()
if cat_id:
    new_material.asset_data.catalog_id = cat_id

if tags:
	for t in tags:
		new_material.asset_data.tags.new(t, skip_if_exists=True)
new_material.asset_data.description = "Material by ambientcg.com"

override = bpy.context.copy()
override["id"] = new_material
print("thumbfile: ", thumbnail_file)
with bpy.context.temp_override(**override):
    bpy.ops.ed.lib_id_load_custom_preview(filepath=thumbnail_file)

bpy.ops.mesh.primitive_plane_add(size=2)
obj = bpy.context.active_object
obj.name = arg_dict["id"]
if obj.data.materials:
	obj.data.materials[0] = new_material
else:
	obj.data.materials.append(new_material)


bpy.context.preferences.filepaths.save_version = 0  # Avoid .blend1
bpy.ops.wm.save_mainfile(relative_remap=True)
