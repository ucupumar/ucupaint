import sys, bpy, os
import shutil


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

# check dir exist or make dir
if not os.path.exists(dir_target):
	os.makedirs(dir_target)

# remove existing directory files
# for filename in os.listdir(dir_target):
# 	file_path = os.path.join(dir_target, filename)
# 	try:
# 		if os.path.isfile(file_path) or os.path.islink(file_path):
# 			os.unlink(file_path)
# 		elif os.path.isdir(file_path):
# 			shutil.rmtree(file_path)
# 	except Exception as e:
# 		print('Failed to delete %s. Reason: %s' % (file_path, e))

# # copy files or directories
# for filename in os.listdir(dir_source):
# 	file_path = os.path.join(dir_source, filename)
# 	if os.path.isfile(file_path) or os.path.islink(file_path):
# 		shutil.copy(file_path, dir_target)
# 	elif os.path.isdir(file_path):
# 		shutil.copytree(file_path, os.path.join(dir_target, filename))

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

new_material = bpy.data.materials.new(name=arg_dict["id"])
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

# Create objects and assign materials
# for i, material in enumerate(materials):
#     bpy.ops.mesh.primitive_plane_add(size=2, location=(i * 3, 0, 0))
#     obj = bpy.context.active_object
#     if obj.data.materials:
#         obj.data.materials[0] = material
#     else:
#         obj.data.materials.append(material)

bpy.context.preferences.filepaths.save_version = 0  # Avoid .blend1
bpy.ops.wm.save_mainfile(relative_remap=True)
