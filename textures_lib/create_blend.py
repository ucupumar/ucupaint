import sys, bpy, os
from mathutils import *


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

output = [n for n in new_material.node_tree.nodes if n.type == 'OUTPUT_MATERIAL' and n.is_active_output]
if output: output = output[0]

normal_dx = None 
normal_gl = None

base_pos = Vector((0, 0))

base_pos.x = bsdf.location.x - 700
base_pos.y = bsdf.location.y

base_pos_extra = Vector((0, 0))
base_pos_extra.x = bsdf.location.x - 300
base_pos_extra.y = bsdf.location.y - 300

id = arg_dict["id"].lower()

for image_path in image_paths:

	print("load image: ", image_path)	
	# Load image
	image = bpy.data.images.load("//"+image_path)

	# Create texture
	base_name = os.path.basename(image_path)

	texture = bpy.data.textures.new(name=base_name, type='IMAGE')
	texture.image = image

	check_name = base_name.lower()
	# remove id from name
	if id in check_name:
		check_name = check_name.replace(id, "")

	update_loc = True
	tex_image = None
	if "color" in check_name:
		tex_image = new_material.node_tree.nodes.new('ShaderNodeTexImage')
		tex_image.image = image
		new_material.node_tree.links.new(bsdf.inputs['Base Color'], tex_image.outputs['Color'])
	elif "normal" in check_name:
		if "dx" in check_name:
			normal_dx = image
		if "gl" in check_name:
			normal_gl = image
		update_loc = False
	elif "metal" in check_name:
		tex_image = new_material.node_tree.nodes.new('ShaderNodeTexImage')
		tex_image.image = image
		new_material.node_tree.links.new(bsdf.inputs['Metallic'], tex_image.outputs['Color'])
	elif "rough" in check_name:
		tex_image = new_material.node_tree.nodes.new('ShaderNodeTexImage')
		tex_image.image = image
		new_material.node_tree.links.new(bsdf.inputs['Roughness'], tex_image.outputs['Color'])
	elif "disp" in check_name:
		tex_image = new_material.node_tree.nodes.new('ShaderNodeTexImage')
		tex_image.image = image

		displacement_node = new_material.node_tree.nodes.new('ShaderNodeDisplacement')
		new_material.node_tree.links.new(displacement_node.inputs['Height'], tex_image.outputs['Color'])
		new_material.node_tree.links.new(output.inputs['Displacement'], displacement_node.outputs['Displacement'])

		displacement_node.location = base_pos_extra
		base_pos_extra.y -= 300
	else:
		update_loc = False

	# Set location
	if tex_image != None and update_loc:
		tex_image.location = base_pos
		base_pos.y -= 300
	
if normal_gl != None or normal_dx != None:
	tex_image = new_material.node_tree.nodes.new('ShaderNodeTexImage')
	normal_node = new_material.node_tree.nodes.new('ShaderNodeNormalMap')

	if normal_gl != None:
		tex_image.image = normal_gl
		new_material.node_tree.links.new(normal_node.inputs['Color'], tex_image.outputs['Color'])
	elif normal_dx != None:
		tex_image.image = normal_dx

	new_material.node_tree.links.new(normal_node.inputs['Color'], tex_image.outputs['Color'])
	new_material.node_tree.links.new(bsdf.inputs['Normal'], normal_node.outputs['Normal'])
	
	normal_node.location = base_pos_extra
	tex_image.location = base_pos

new_material.asset_mark()
if cat_id:
    new_material.asset_data.catalog_id = cat_id

if tags:
	for t in tags:
		new_material.asset_data.tags.new(t, skip_if_exists=True)
new_material.asset_data.description = "Material by ambientcg.com"

override = bpy.context.copy()
override["id"] = new_material

thumbnail_file = os.path.join(dir_target, arg_dict["id"]+".png")
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
