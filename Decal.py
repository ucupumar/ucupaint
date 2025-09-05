import bpy, re
from . import lib
from bpy.props import *
from bpy.app.handlers import persistent
from .common import *

def get_decal_object(entity):
    m1 = re.match(r'^yp\.layers\[(\d+)\]$', entity.path_from_id())
    m2 = re.match(r'^yp\.layers\[(\d+)\]\.masks\[(\d+)\]$', entity.path_from_id())

    if m1: tree = get_tree(entity)
    elif m2: tree = get_mask_tree(entity)
    else: return None

    decal_obj = None
    texcoord = tree.nodes.get(entity.texcoord)
    if texcoord and hasattr(texcoord, 'object'): decal_obj = texcoord.object

    return decal_obj

def get_decal_constraint(decal_obj):
    cs = [c for c in decal_obj.constraints if c.type == 'SHRINKWRAP']
    if len(cs) > 0: return cs[0]
    return None

def any_decal_inside_layer(layer):
    if layer.texcoord_type == 'Decal':
        return True

    for mask in layer.masks:
        if mask.texcoord_type == 'Decal':
            return True

    return False

def remove_decal_object(tree, entity):
    if not tree: return
    # NOTE: This will remove the texcoord object even if the entity is not using decal
    #if entity.texcoord_type == 'Decal':
    texcoord = tree.nodes.get(entity.texcoord)
    if texcoord and hasattr(texcoord, 'object') and texcoord.object:
        decal_obj = texcoord.object
        if decal_obj.type == 'EMPTY' and decal_obj.users <= 2:
            texcoord.object = None
            remove_datablock(bpy.data.objects, decal_obj)

def create_decal_empty():
    obj = bpy.context.object
    scene = bpy.context.scene
    empty_name = get_unique_name('Decal', bpy.data.objects)
    empty = bpy.data.objects.new(empty_name, None)
    if is_bl_newer_than(2, 80):
        empty.empty_display_type = 'SINGLE_ARROW'
    else: empty.empty_draw_type = 'SINGLE_ARROW'
    custom_collection = obj.users_collection[0] if is_bl_newer_than(2, 80) and len(obj.users_collection) > 0 else None
    link_object(scene, empty, custom_collection)
    if is_bl_newer_than(2, 80):
        empty.location = scene.cursor.location.copy()
        empty.rotation_euler = scene.cursor.rotation_euler.copy()
    else: 
        empty.location = scene.cursor_location.copy()

    # Parent empty to active object
    empty.parent = obj
    empty.matrix_parent_inverse = obj.matrix_world.inverted()

    return empty

def check_entity_decal_nodes(entity, tree=None):
    yp = entity.id_data.yp
    m1 = re.match(r'^yp\.layers\[(\d+)\]$', entity.path_from_id())
    m2 = re.match(r'^yp\.layers\[(\d+)\]\.masks\[(\d+)\]$', entity.path_from_id())

    if m1: 
        entity_enabled = get_layer_enabled(entity)
        source = get_layer_source(entity)
        if not tree: tree = get_tree(entity)
        layer = entity
        mask = None
    elif m2: 
        entity_enabled = get_mask_enabled(entity)
        source = get_mask_source(entity)
        layer = yp.layers[int(m2.group(1))]
        if not tree: tree = get_tree(entity)
        mask = entity
    else: return

    # Get height channel
    height_ch = get_height_channel(layer)

    # Create texcoord node if decal is used
    texcoord = tree.nodes.get(entity.texcoord)
    if entity_enabled and entity.texcoord_type == 'Decal' and is_mapping_possible(entity.type):

        # Set image extension type to clip
        image = None
        if entity.type == 'IMAGE' and source:
            image = source.image

        # Create new empty object if there's no texcoord yet
        if not texcoord:
            empty = create_decal_empty()
            texcoord = new_node(tree, entity, 'texcoord', 'ShaderNodeTexCoord', 'TexCoord')
            texcoord.object = empty

        decal_process = tree.nodes.get(entity.decal_process)
        if not decal_process:
            decal_process = new_node(tree, entity, 'decal_process', 'ShaderNodeGroup', 'Decal Process')
            decal_process.node_tree = get_node_tree_lib(lib.DECAL_PROCESS)

            # Set image extension only after decal process node is initialized
            if image and source:
                entity.original_image_extension = source.extension
                source.extension = 'CLIP'

        # Set decal aspect ratio
        if image and image.size[0] > 0 and image.size[1] > 0:
            if image.size[0] > image.size[1]:
                decal_process.inputs['Scale'].default_value = (image.size[1] / image.size[0], 1.0, 1.0)
            else: decal_process.inputs['Scale'].default_value = (1.0, image.size[0] / image.size[1], 1.0)

        # Create decal alpha nodes
        if mask:

            # Check if height channel is enabled
            height_root_ch = get_root_height_channel(yp)
            height_ch_enabled = get_channel_enabled(height_ch) if height_ch else False

            decal_alpha = check_new_node(tree, mask, 'decal_alpha', 'ShaderNodeMath', 'Decal Alpha')
            if decal_alpha.operation != 'MULTIPLY':
                decal_alpha.operation = 'MULTIPLY'

            if height_ch and height_ch_enabled and height_root_ch.enable_smooth_bump:
                for letter in nsew_letters:
                    decal_alpha = check_new_node(tree, mask, 'decal_alpha_' + letter, 'ShaderNodeMath', 'Decal Alpha ' + letter.upper())
                    if decal_alpha.operation != 'MULTIPLY':
                        decal_alpha.operation = 'MULTIPLY'
            else:
                for letter in nsew_letters:
                    remove_node(tree, mask, 'decal_alpha_' + letter)

        else:

            for i, ch in enumerate(layer.channels):
                root_ch = yp.channels[i]
                ch_enabled = get_channel_enabled(ch)
                if ch_enabled:
                    decal_alpha = check_new_node(tree, ch, 'decal_alpha', 'ShaderNodeMath', 'Decal Alpha')
                    if decal_alpha.operation != 'MULTIPLY':
                        decal_alpha.operation = 'MULTIPLY'
                else:
                    remove_node(tree, ch, 'decal_alpha')

                if root_ch.type == 'NORMAL':
                    if ch_enabled and root_ch.enable_smooth_bump:
                        for letter in nsew_letters:
                            decal_alpha = check_new_node(tree, ch, 'decal_alpha_' + letter, 'ShaderNodeMath', 'Decal Alpha ' + letter.upper())
                            if decal_alpha.operation != 'MULTIPLY':
                                decal_alpha.operation = 'MULTIPLY'
                    else:
                        for letter in nsew_letters:
                            remove_node(tree, ch, 'decal_alpha_' + letter)
    else:

        if not texcoord or not hasattr(texcoord, 'object') or not texcoord.object: 
            remove_node(tree, entity, 'texcoord')
        remove_node(tree, entity, 'decal_process')

        if mask: 
            remove_node(tree, mask, 'decal_alpha')

            if height_ch:
                for letter in nsew_letters:
                    remove_node(tree, mask, 'decal_alpha_' + letter)
        else:
            for i, ch in enumerate(layer.channels):
                root_ch = yp.channels[i]
                remove_node(tree, ch, 'decal_alpha')

                if root_ch.type == 'NORMAL':
                    for letter in nsew_letters:
                        remove_node(tree, ch, 'decal_alpha_' + letter)

        # Recover image extension type
        if entity.type == 'IMAGE' and entity.original_texcoord == 'Decal' and entity.original_image_extension != '':
            source = get_mask_source(mask) if mask else get_layer_source(layer)
            if source:
                source.extension = entity.original_image_extension
                entity.original_image_extension = ''

    # Save original texcoord type
    if entity.original_texcoord != entity.texcoord_type:
        entity.original_texcoord = entity.texcoord_type

class YSelectDecalObject(bpy.types.Operator):
    bl_idname = "wm.y_select_decal_object"
    bl_label = "Select Decal Object"
    bl_description = "Select Decal Object"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        group_node = get_active_ypaint_node()
        return group_node and hasattr(context, 'entity')

    def execute(self, context):
        scene = context.scene

        decal_obj = get_decal_object(context.entity)
        if decal_obj:
            try: bpy.ops.object.mode_set(mode='OBJECT')
            except: pass
            bpy.ops.object.select_all(action='DESELECT')
            if decal_obj.name not in get_scene_objects():
                parent = decal_obj.parent
                custom_collection = parent.users_collection[0] if is_bl_newer_than(2, 80) and parent and len(parent.users_collection) > 0 else None
                link_object(scene, decal_obj, custom_collection)
            set_active_object(decal_obj)
            set_object_select(decal_obj, True)
        else: return {'CANCELLED'}

        return {'FINISHED'}

class YSetDecalObjectPositionToCursor(bpy.types.Operator):
    bl_idname = "wm.y_set_decal_object_position_to_sursor"
    bl_label = "Set Decal Position to Cursor"
    bl_description = "Set the position of the decal object to the 3D cursor"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        group_node = get_active_ypaint_node()
        return group_node and hasattr(context, 'entity')

    def execute(self, context):
        scene = bpy.context.scene
        entity = context.entity

        m1 = re.match(r'^yp\.layers\[(\d+)\]$', entity.path_from_id())
        m2 = re.match(r'^yp\.layers\[(\d+)\]\.masks\[(\d+)\]$', entity.path_from_id())

        if m1: tree = get_tree(entity)
        elif m2: tree = get_mask_tree(entity)
        else: return {'CANCELLED'}

        texcoord = tree.nodes.get(entity.texcoord)

        if texcoord and hasattr(texcoord, 'object') and texcoord.object:
            # Move decal object to 3D cursor
            if is_bl_newer_than(2, 80):
                texcoord.object.location = scene.cursor.location.copy()
                texcoord.object.rotation_euler = scene.cursor.rotation_euler.copy()
            else: 
                texcoord.object.location = scene.cursor_location.copy()

        else: return {'CANCELLED'}

        return {'FINISHED'}

class BaseDecal():

    decal_distance_value : FloatProperty(
        name = 'Decal Distance',
        description = 'Distance between surface and the decal object',
        min=0.0, max=100.0, default=0.5, precision=3
    )

    original_texcoord : EnumProperty(
        name = 'Original Texture Coordinate Type',
        items = texcoord_type_items,
        default = 'UV'
    )

    original_image_extension : StringProperty(
        name = 'Original Image Extension Type',
        default = ''
    )

def register():
    bpy.utils.register_class(YSelectDecalObject)
    bpy.utils.register_class(YSetDecalObjectPositionToCursor)

def unregister():
    bpy.utils.unregister_class(YSelectDecalObject)
    bpy.utils.unregister_class(YSetDecalObjectPositionToCursor)
