import bpy, re, time, math, numpy
from bpy.props import *
from mathutils import *
from .common import *
from .bake_common import *
from .subtree import *
from .node_connections import *
from .node_arrangements import *
from .input_outputs import *
from . import lib, Layer, Mask, Modifier, MaskModifier, image_ops, ListItem

def transfer_uv(objs, mat, entity, uv_map, is_entity_baked=False):

    yp = entity.id_data.yp
    scene = bpy.context.scene

    # Check entity
    m1 = re.match(r'^yp\.layers\[(\d+)\]$', entity.path_from_id())
    m2 = re.match(r'^yp\.layers\[(\d+)\]\.masks\[(\d+)\]$', entity.path_from_id())

    if m1: 
        if is_entity_baked:
            tree = get_tree(entity)
            source = tree.nodes.get(entity.baked_source)
        else: source = get_layer_source(entity)
        mapping = get_layer_mapping(entity)
        index = int(m1.group(1))
    elif m2: 
        if is_entity_baked:
            tree = get_mask_tree(entity)
            source = tree.nodes.get(entity.baked_source)
        else: source = get_mask_source(entity)
        mapping = get_mask_mapping(entity)
        index = int(m2.group(2))
    else: return

    image = source.image
    if not image: return

    # Merge objects if necessary
    temp_objs = []
    if len(objs) > 1 and not is_join_objects_problematic(yp):
        objs = temp_objs = [get_merged_mesh_objects(scene, objs)]

    # Set active uv
    for obj in objs:
        uv_layers = get_uv_layers(obj)
        uv_layers.active = uv_layers.get(uv_map)

    # Get tile numbers
    tilenums = UDIM.get_tile_numbers(objs, uv_map)

    # Get image settings
    segment = None
    use_alpha = False
    if image.yia.is_image_atlas and entity.segment_name != '':
        segment = image.yia.segments.get(entity.segment_name)
        width = segment.width
        height = segment.height
        if image.yia.color == 'WHITE':
            col = (1.0, 1.0, 1.0, 1.0)
        elif image.yia.color == 'BLACK':
            col = (0.0, 0.0, 0.0, 1.0)
        else: 
            col = (0.0, 0.0, 0.0, 0.0)
            use_alpha = True
    elif image.yua.is_udim_atlas and entity.segment_name != '':
        segment = image.yua.segments.get(entity.segment_name)
        segment_tilenums = UDIM.get_udim_segment_tilenums(segment)

        # Get the highest resolution
        for i, st in enumerate(segment_tilenums):
            if i == 0 : width = height = 1
            tile = image.tiles.get(st)
            if tile.size[0] > width: width = tile.size[0]
            if tile.size[1] > height: height = tile.size[1]

        col = segment.base_color
        use_alpha = True if col[3] < 0.5 else False
    else:
        width = image.size[0]
        height = image.size[1]
        # Change color if baked image is found
        if 'Pointiness' in image.name:
            col = (0.73, 0.73, 0.73, 1.0)
        elif 'AO' in image.name:
            col = (1.0, 1.0, 1.0, 1.0)
        elif m2: 
            col = get_image_mask_base_color(entity, image, index)
        else:
            col = (0.0, 0.0, 0.0, 0.0)
            use_alpha = True

    # Create temp image as bake target
    if len(tilenums) > 1 or (segment and image.source == 'TILED'):
        temp_image = bpy.data.images.new(
            name='__TEMP', width=width, height=height,
            alpha=True, float_buffer=image.is_float, tiled=True
        )

        # Fill tiles
        for tilenum in tilenums:
            UDIM.fill_tile(temp_image, tilenum, col, width, height)

        # Initial pack
        if image.yua.is_udim_atlas:
            UDIM.initial_pack_udim(temp_image, col)
        else: UDIM.initial_pack_udim(temp_image, col, image.name)

    else:
        temp_image = bpy.data.images.new(
            name='__TEMP', width=width, height=height,
            alpha=True, float_buffer=image.is_float
        )

    temp_image.colorspace_settings.name = image.colorspace_settings.name
    temp_image.generated_color = col

    # Create bake nodes
    tex = mat.node_tree.nodes.new('ShaderNodeTexImage')
    emit = mat.node_tree.nodes.new('ShaderNodeEmission')

    # Set image to temp nodes
    src = mat.node_tree.nodes.new('ShaderNodeTexImage')
    src.image = image
    src_uv = mat.node_tree.nodes.new('ShaderNodeUVMap')
    src_uv.uv_map = entity.uv_name

    # Copy mapping
    mapp = mat.node_tree.nodes.new('ShaderNodeMapping')

    if is_bl_newer_than(2, 81):
        mapp.inputs[1].default_value[0] = mapping.inputs[1].default_value[0]
        mapp.inputs[1].default_value[1] = mapping.inputs[1].default_value[1]
        mapp.inputs[1].default_value[2] = mapping.inputs[1].default_value[2]

        mapp.inputs[2].default_value[0] = mapping.inputs[2].default_value[0]
        mapp.inputs[2].default_value[1] = mapping.inputs[2].default_value[1]
        mapp.inputs[2].default_value[2] = mapping.inputs[2].default_value[2]

        mapp.inputs[3].default_value[0] = mapping.inputs[3].default_value[0]
        mapp.inputs[3].default_value[1] = mapping.inputs[3].default_value[1]
        mapp.inputs[3].default_value[2] = mapping.inputs[3].default_value[2]
    else:
        mapp.translation[0] = mapping.translation[0]
        mapp.translation[1] = mapping.translation[1]
        mapp.translation[2] = mapping.translation[2]

        mapp.rotation[0] = mapping.rotation[0]
        mapp.rotation[1] = mapping.rotation[1]
        mapp.rotation[2] = mapping.rotation[2]

        mapp.scale[0] = mapping.scale[0]
        mapp.scale[1] = mapping.scale[1]
        mapp.scale[2] = mapping.scale[2]

    # Get material output
    output = get_active_mat_output_node(mat.node_tree)
    ori_bsdf = output.inputs[0].links[0].from_socket

    straight_over = None
    if use_alpha:
        straight_over = mat.node_tree.nodes.new('ShaderNodeGroup')
        straight_over.node_tree = get_node_tree_lib(lib.STRAIGHT_OVER)
        straight_over.inputs[1].default_value = 0.0

    # Set temp image node
    tex.image = temp_image
    mat.node_tree.nodes.active = tex

    # Links
    if not is_entity_baked:
        mat.node_tree.links.new(src_uv.outputs[0], mapp.inputs[0])
        mat.node_tree.links.new(mapp.outputs[0], src.inputs[0])
    else: mat.node_tree.links.new(src_uv.outputs[0], src.inputs[0])
    rgb = src.outputs[0]
    alpha = src.outputs[1]
    if straight_over:
        mat.node_tree.links.new(rgb, straight_over.inputs[2])
        mat.node_tree.links.new(alpha, straight_over.inputs[3])
        rgb = straight_over.outputs[0]

    mat.node_tree.links.new(rgb, emit.inputs[0])
    mat.node_tree.links.new(emit.outputs[0], output.inputs[0])

    # Bake!
    bake_object_op()

    # Bake alpha if using alpha
    if use_alpha:

        # Create another temp image
        temp_image1 = temp_image.copy()
        tex.image = temp_image1

        if temp_image1.source == 'TILED':
            temp_image1.name = '__TEMP1'
            UDIM.initial_pack_udim(temp_image1)

        mat.node_tree.links.new(src.outputs[1], emit.inputs[0])

        # Temp image should use linear to properly bake alpha
        temp_image1.colorspace_settings.name = get_noncolor_name()

        # Bake again!
        bake_object_op()

        # Set tile pixels
        for tilenum in tilenums:

            # Swap tile
            if tilenum != 1001:
                UDIM.swap_tile(temp_image, 1001, tilenum)
                UDIM.swap_tile(temp_image1, 1001, tilenum)

            # Copy the result to original temp image
            copy_image_channel_pixels(temp_image1, temp_image, 0, 3)

            # Swap tile again to recover
            if tilenum != 1001:
                UDIM.swap_tile(temp_image, 1001, tilenum)
                UDIM.swap_tile(temp_image1, 1001, tilenum)

        # Remove temp image 1
        remove_datablock(bpy.data.images, temp_image1, user=tex, user_prop='image')

    if segment and image.source == 'TILED':

        # Remove original segment
        UDIM.remove_udim_atlas_segment_by_name(image, segment.name, yp)

        # Create new segment
        new_segment = UDIM.get_set_udim_atlas_segment(
            tilenums, 
            width=width, height=height, color=col, 
            colorspace=image.colorspace_settings.name, hdr=image.is_float, yp=yp, 
            source_image=temp_image, source_tilenums=tilenums
        )

        # Set image
        if image != new_segment.id_data:
            source.image = new_segment.id_data

        # Remove temp image
        remove_datablock(bpy.data.images, temp_image, user=tex, user_prop='image')

    elif temp_image.source == 'TILED' or image.source == 'TILED':
        # Replace image if any of the images is using UDIM
        replace_image(image, temp_image)
    else:
        # Copy back temp/baked image to original image
        copy_image_pixels(temp_image, image, segment)

        # Remove temp image
        remove_datablock(bpy.data.images, temp_image, user=tex, user_prop='image')

    # HACK: Pack and refresh to update image in Blender 2.77 and lower
    if not is_bl_newer_than(2, 78) and (image.packed_file or image.filepath == ''):
        if image.is_float:
            image_ops.pack_float_image(image)
        else: image.pack(as_png=True)
        image.reload()

    # Remove temp nodes
    simple_remove_node(mat.node_tree, tex)
    simple_remove_node(mat.node_tree, emit)
    simple_remove_node(mat.node_tree, src)
    simple_remove_node(mat.node_tree, src_uv)
    simple_remove_node(mat.node_tree, mapp)
    if straight_over:
        simple_remove_node(mat.node_tree, straight_over)

    mat.node_tree.links.new(ori_bsdf, output.inputs[0])

    if not is_entity_baked:
        # Update entity transform
        entity.translation = (0.0, 0.0, 0.0)
        entity.rotation = (0.0, 0.0, 0.0)
        entity.scale = (1.0, 1.0, 1.0)

        # Update mapping
        update_mapping(entity)

    # Change uv of entity
    entity.uv_name = uv_map

    # Remove temporary objects
    if temp_objs:
        for o in temp_objs:
            remove_mesh_obj(o)

def set_entities_which_using_the_same_image_or_segment(entity, target_uv_name):
    yp = entity.id_data.yp

    if entity.type == 'IMAGE':
        m = re.match(r'yp\.layers\[(\d+)\]\.masks\[(\d+)\]', entity.path_from_id())

        if m: source = get_mask_source(entity)
        else: source = get_layer_source(entity)

        image = source.image
        segment_mix_name = image.name + entity.segment_name if image and (image.yia.is_image_atlas or image.yua.is_udim_atlas) else ''

        for layer in yp.layers:

            for mask in layer.masks:
                if mask == entity or mask.type != 'IMAGE': continue
                src = get_mask_source(mask)
                img = src.image

                if img.yia.is_image_atlas or img.yua.is_udim_atlas:
                    if img.name + mask.segment_name == segment_mix_name:
                        mask.uv_name = target_uv_name
                else:
                    if img == image:
                        mask.uv_name = target_uv_name

            if layer == entity or layer.type != 'IMAGE': continue
            src = get_layer_source(layer)
            img = src.image

            if img.yia.is_image_atlas or img.yua.is_udim_atlas:
                if img.name + layer.segment_name == segment_mix_name:
                    layer.uv_name = target_uv_name
            else:
                if img == image:
                    layer.uv_name = target_uv_name

def get_entities_to_transfer(yp, from_uv_map, to_uv_map):

    # Check the same images used by multiple layers or masks
    used_images = []
    used_segments = []
    entities = []
    for layer in yp.layers:
        if layer.baked_source != '' and layer.baked_uv_name == from_uv_map:
            if layer not in entities: entities.append(layer)

        if layer.type == 'IMAGE' and layer.uv_name == from_uv_map:
            source = get_layer_source(layer)
            if source and source.image:
                image = source.image

                if image.yia.is_image_atlas or image.yua.is_udim_atlas:
                    if image.name + layer.segment_name not in used_segments:
                        used_segments.append(image.name + layer.segment_name)
                        if layer not in entities: entities.append(layer)
                else: 
                    if image not in used_images:
                        used_images.append(image)
                        if layer not in entities: entities.append(layer)

                if layer not in entities:
                    layer.uv_name = to_uv_map
        
        for mask in layer.masks:
            if mask.baked_source != '' and mask.baked_uv_name == from_uv_map:
                if mask not in entities: entities.append(mask)

            if mask.type == 'IMAGE' and mask.uv_name == from_uv_map:

                source = get_mask_source(mask)
                if source and source.image:
                    image = source.image

                    if image.yia.is_image_atlas or image.yua.is_udim_atlas:
                        if image.name + mask.segment_name not in used_segments:
                            used_segments.append(image.name + mask.segment_name)
                            if mask not in entities: entities.append(mask)
                    else: 
                        if image not in used_images:
                            used_images.append(image)
                            if mask not in entities: entities.append(mask)

                    if mask not in entities:
                        mask.uv_name = to_uv_map

    return entities

class YTransferSomeLayerUV(bpy.types.Operator, BaseBakeOperator):
    bl_idname = "wm.y_transfer_some_layer_uv"
    bl_label = "Transfer Some Layer UV"
    bl_description = "Transfer some layers/masks UV by baking it to other uv (this will take quite some time to finish)"
    bl_options = {'REGISTER', 'UNDO'}

    from_uv_map : StringProperty(default='')
    uv_map : StringProperty(default='')
    uv_map_coll : CollectionProperty(type=bpy.types.PropertyGroup)

    remove_from_uv : BoolProperty(
        name = 'Delete From UV',
        description = "Remove 'From UV' from objects",
        default = False
    )

    reorder_uv_list : BoolProperty(
        name = 'Reorder UV',
        description = "Reorder 'To UV' so it will have the same index as 'From UV'",
        default = True
    )

    @classmethod
    def poll(cls, context):
        return get_active_ypaint_node() and context.object.type == 'MESH' # and hasattr(context, 'layer')

    def invoke(self, context, event):
        self.invoke_operator(context)

        obj = self.obj = context.object
        scene = self.scene = context.scene

        if hasattr(context, 'mask'):
            self.entity = context.mask

        elif hasattr(context, 'layer'):
            self.entity = context.layer

        # Use active uv layer name by default
        uv_layers = get_uv_layers(obj)

        # UV Map collections update
        self.uv_map_coll.clear()
        for uv in uv_layers:
            if not uv.name.startswith(TEMP_UV):
                self.uv_map_coll.add().name = uv.name

        self.from_uv_map = self.entity.uv_name

        return context.window_manager.invoke_props_dialog(self, width=320)

    def check(self, context):
        return True

    def draw(self, context):

        row = split_layout(self.layout, 0.4)

        col = row.column(align=False)
        col.label(text='From UV:')
        col.label(text='To UV:')
        col.label(text='Samples:')

        col.label(text='Margin:')

        col.label(text='')

        if self.remove_from_uv:
            col.label(text='')

        col = row.column(align=False)
        col.prop_search(self, "from_uv_map", self, "uv_map_coll", text='', icon='GROUP_UVS')
        col.prop_search(self, "uv_map", self, "uv_map_coll", text='', icon='GROUP_UVS')
        col.prop(self, 'samples', text='')

        if is_bl_newer_than(3, 1):
            split = split_layout(col, 0.4, align=True)
            split.prop(self, 'margin', text='')
            split.prop(self, 'margin_type', text='')
        else:
            col.prop(self, 'margin', text='')

        col.prop(self, 'remove_from_uv')

        if self.remove_from_uv:
            col.prop(self, 'reorder_uv_list')

    def execute(self, context):
        if not self.is_cycles_exist(context): return {'CANCELLED'}

        T = time.time()

        if self.from_uv_map == '' or self.uv_map == '':
            self.report({'ERROR'}, "From or To UV Map cannot be empty!")
            return {'CANCELLED'}

        if self.from_uv_map == self.uv_map:
            self.report({'ERROR'}, "From and To UV cannot have same value!")
            return {'CANCELLED'}

        mat = get_active_material()
        node = get_active_ypaint_node()
        yp = node.node_tree.yp
        objs = get_all_objects_with_same_materials(mat)

        # Check if all uv are available on all objects
        for obj in objs:
            uv_layers = get_uv_layers(obj)
            from_uv = uv_layers.get(self.from_uv_map)
            to_uv = uv_layers.get(self.uv_map)
            if not from_uv or not to_uv:
                self.report({'ERROR'}, "Some uvs are not found in some objects!")
                return {'CANCELLED'}

        # Prepare bake settings
        book = remember_before_bake(yp)
        prepare_bake_settings(
            book, objs, yp, samples=self.samples, margin=self.margin, 
            uv_map=self.uv_map, bake_type='EMIT', bake_device=self.bake_device, margin_type=self.margin_type
        )
        
        # Get entites to transfer
        entities = get_entities_to_transfer(yp, self.from_uv_map, self.uv_map)

        for entity in entities:
            if entity.type == 'IMAGE':

                print('TRANSFER UV: Transferring entity ' + entity.name + '...')
                transfer_uv(objs, mat, entity, self.uv_map)

            if entity.baked_source != '':
                print('TRANSFER UV: Transferring baked entity ' + entity.name + '...')
                transfer_uv(objs, mat, entity, self.uv_map, is_entity_baked=True)

            if entity.uv_name != self.uv_map:
                entity.uv_name = self.uv_map

        #return {'FINISHED'}

        if self.remove_from_uv:
            for obj in objs:
                uv_layers = get_uv_layers(obj)
                ori_index = get_uv_layer_index(obj, self.from_uv_map)
                from_uv = uv_layers.get(self.from_uv_map)
                uv_layers.remove(from_uv)

                # Reorder UV
                if self.reorder_uv_list and ori_index != -1:
                    uv_index = get_uv_layer_index(obj, self.uv_map)
                    if ori_index > uv_index:
                        ori_index -= 1
                    move_uv(obj, uv_index, ori_index)

        # Recover bake settings
        recover_bake_settings(book, yp)

        # Check height channel uv
        height_ch = get_root_height_channel(yp)
        if height_ch and height_ch.main_uv == self.from_uv_map:
            height_ch.main_uv = self.uv_map
            #height_ch.enable_smooth_bump = height_ch.enable_smooth_bump

        # Refresh mapping and stuff
        yp.active_layer_index = yp.active_layer_index

        print(
            'INFO: All layers and masks using', self.from_uv_map,
            'are transferred to', self.uv_map,
            'in', '{:0.2f}'.format(time.time() - T), 'seconds!'
        )

        return {'FINISHED'}

class YTransferLayerUV(bpy.types.Operator, BaseBakeOperator):
    bl_idname = "wm.y_transfer_layer_uv"
    bl_label = "Transfer Layer UV"
    bl_description = "Transfer Layer UV by baking it to other uv (this will take quite some time to finish)"
    bl_options = {'REGISTER', 'UNDO'}

    uv_map : StringProperty(default='')
    uv_map_coll : CollectionProperty(type=bpy.types.PropertyGroup)

    @classmethod
    def poll(cls, context):
        return get_active_ypaint_node() and context.object.type == 'MESH' # and hasattr(context, 'layer')

    def invoke(self, context, event):
        self.invoke_operator(context)

        obj = self.obj = context.object
        scene = self.scene = context.scene

        if hasattr(context, 'mask'):
            self.entity = context.mask

        elif hasattr(context, 'layer'):
            self.entity = context.layer

        if not self.entity:
            return self.execute(context)

        # Use active uv layer name by default
        uv_layers = get_uv_layers(obj)

        # UV Map collections update
        self.uv_map_coll.clear()
        for uv in uv_layers:
            if not uv.name.startswith(TEMP_UV) and uv.name != self.entity.uv_name:
                self.uv_map_coll.add().name = uv.name

        return context.window_manager.invoke_props_dialog(self, width=320)

    def check(self, context):
        return True

    def draw(self, context):
        row = split_layout(self.layout, 0.4)

        col = row.column(align=False)
        col.label(text='Target UV:')
        col.label(text='Samples:')
        col.label(text='Margin:')

        col = row.column(align=False)
        col.prop_search(self, "uv_map", self, "uv_map_coll", text='', icon='GROUP_UVS')
        col.prop(self, 'samples', text='')

        if is_bl_newer_than(3, 1):
            split = split_layout(col, 0.4, align=True)
            split.prop(self, 'margin', text='')
            split.prop(self, 'margin_type', text='')
        else:
            col.prop(self, 'margin', text='')

    def execute(self, context):
        if not self.is_cycles_exist(context): return {'CANCELLED'}

        T = time.time()

        if not hasattr(self, 'entity'):
            return {'CANCELLED'}

        if self.entity.type != 'IMAGE' or self.entity.texcoord_type != 'UV':
            self.report({'ERROR'}, "Only works with image layer/mask with UV Mapping")
            return {'CANCELLED'}

        if self.uv_map == '':
            self.report({'ERROR'}, "Target UV Map cannot be empty!")
            return {'CANCELLED'}

        if self.uv_map == self.entity.uv_name:
            self.report({'ERROR'}, "This layer/mask already use " + self.uv_map + "!")
            return {'CANCELLED'}

        mat = get_active_material()
        yp = self.entity.id_data.yp
        objs = get_all_objects_with_same_materials(mat)

        # Prepare bake settings
        book = remember_before_bake(yp)
        prepare_bake_settings(
            book, objs, yp, samples=self.samples, margin=self.margin, 
            uv_map=self.uv_map, bake_type='EMIT', bake_device=self.bake_device, margin_type=self.margin_type
        )

        if self.entity.type == 'IMAGE':
            # Set other entites uv that using the same image or segment
            set_entities_which_using_the_same_image_or_segment(self.entity, self.uv_map)

            # Transfer UV
            #for ent in entities:
            transfer_uv(objs, mat, self.entity, self.uv_map)

        if self.entity.baked_source != '':
            transfer_uv(objs, mat, self.entity, self.uv_map, is_entity_baked=True)

        # Recover bake settings
        recover_bake_settings(book, yp)

        # Refresh mapping and stuff
        yp.active_layer_index = yp.active_layer_index

        print(
            'INFO:', self.entity.name,
            'UV is transferred from', self.entity.uv_name,
            'to', self.uv_map,
            'in', '{:0.2f}'.format(time.time() - T), 'seconds!'
        )

        return {'FINISHED'}

def get_resize_image_entity_and_image(self, context):
    yp = get_active_ypaint_node().node_tree.yp
    entity = yp.layers.get(self.layer_name)
    image = bpy.data.images.get(self.image_name)

    if entity:
        for mask in entity.masks:
            if mask.active_edit:
                entity = mask
                break
    
    return entity, image

def update_resize_image_tile_number(self, context):
    entity, image = get_resize_image_entity_and_image(self, context)

    if image and image.source == 'TILED':
        tile = image.tiles.get(int(self.tile_number))
        if tile:
            self.width = tile.size[0]
            self.height = tile.size[1]

class YResizeImage(bpy.types.Operator, BaseBakeOperator):
    bl_idname = "wm.y_resize_image"
    bl_label = "Resize Image Layer/Mask"
    bl_description = "Resize image of layer or mask"
    bl_options = {'REGISTER', 'UNDO'}

    layer_name : StringProperty(default='')
    image_name : StringProperty(default='')

    width : IntProperty(name='Width', default=1024, min=1, max=16384)
    height : IntProperty(name='Height', default=1024, min=1, max=16384)

    all_tiles : BoolProperty(
        name = 'Resize All Tiles',
        description = 'Resize all tiles (when using UDIM atlas, only segment tiles will be resized)',
        default = False
    )

    tile_number : EnumProperty(
        name = 'Tile Number',
        description = 'Tile number that will be resized',
        items = UDIM.udim_tilenum_items,
        update = update_resize_image_tile_number
    )

    @classmethod
    def poll(cls, context):
        return get_active_ypaint_node() and context.object.type == 'MESH'

    def invoke(self, context, event):
        self.invoke_operator(context)

        entity, image = get_resize_image_entity_and_image(self, context)

        if image:
            self.width = image.size[0]
            self.height = image.size[1]

            if image.source == 'TILED':
                tile = image.tiles.get(int(self.tile_number))
                if tile:
                    self.width = tile.size[0]
                    self.height = tile.size[1]

            elif entity and image.yia.is_image_atlas:
                segment = image.yia.segments.get(entity.segment_name)
                self.width = segment.width
                self.height = segment.height

        return context.window_manager.invoke_props_dialog(self, width=320)

    def draw(self, context):
        image = bpy.data.images.get(self.image_name)

        row = split_layout(self.layout, 0.4)

        col = row.column(align=False)

        col.label(text='Width:')
        col.label(text='Height:')

        if image:
            if image.yia.is_image_atlas or not is_bl_newer_than(2, 81):
                col.label(text='Samples:')

            if image.source == 'TILED':
                col.label(text='')
                if not self.all_tiles:
                    col.label(text='Tile Number:')

        col = row.column(align=False)

        col.prop(self, 'width', text='')
        col.prop(self, 'height', text='')

        if image:
            if image.yia.is_image_atlas or not is_bl_newer_than(2, 81):
                col.prop(self, 'samples', text='')

            if image.source == 'TILED':
                if image.yua.is_udim_atlas:
                    col.prop(self, 'all_tiles', text='Resize All Atlas Segment Tiles')
                else: col.prop(self, 'all_tiles')
                if not self.all_tiles:
                    col.prop(self, 'tile_number', text='')

    def execute(self, context):
        if not self.is_cycles_exist(context): return {'CANCELLED'}

        yp = get_active_ypaint_node().node_tree.yp
        entity, image = get_resize_image_entity_and_image(self, context)

        if not entity or not image:
            self.report({'ERROR'}, "There is no active image!")
            return {'CANCELLED'}

        # Get original size
        segment = None
        if image.yia.is_image_atlas:
            segment = image.yia.segments.get(entity.segment_name)
            ori_width = segment.width
            ori_height = segment.height
        if image.source == 'TILED':
            tile = image.tiles.get(int(self.tile_number))
            ori_width = tile.size[0]
            ori_height = tile.size[1]
        else:
            ori_width = image.size[0]
            ori_height = image.size[1]

        if ori_width == self.width and ori_height == self.height:
            self.report({'ERROR'}, "This image already had the same size!")
            return {'CANCELLED'}

        override_context = None
        space = None
        ori_space_image = None

        if not image.yia.is_image_atlas and is_bl_newer_than(2, 81):

            tilenums = [int(self.tile_number)]
            if image.source == 'TILED' and self.all_tiles:
                if image.yua.is_udim_atlas:
                    segment = image.yua.segments.get(entity.segment_name)
                    tilenums = UDIM.get_udim_segment_tilenums(segment)
                else:
                    tilenums = [t.number for t in image.tiles]

            ori_ui_type = bpy.context.area.ui_type
            bpy.context.area.ui_type = 'UV'
            bpy.context.space_data.image = image

            for tilenum in tilenums:
                if image.source == 'TILED':
                    tile = image.tiles.get(tilenum)
                    if not tile: continue
                    image.tiles.active = tile

                bpy.ops.image.resize(size=(self.width, self.height))

            bpy.context.area.ui_type = ori_ui_type

        else:
            scaled_img, new_segment = resize_image(
                image, self.width, self.height, image.colorspace_settings.name,
                self.samples, 0, segment, bake_device=self.bake_device, yp=yp
            )

            if new_segment:
                entity.segment_name = new_segment.name
                source = get_entity_source(entity)
                source.image = scaled_img
                segment.unused = True
                update_mapping(entity)

        # Update UV neighbor resolution
        set_uv_neighbor_resolution(entity)

        # Refresh active layer
        yp.active_layer_index = yp.active_layer_index

        return {'FINISHED'}

class YBakeChannelToVcol(bpy.types.Operator, BaseBakeOperator):
    """Bake Channel to Vertex Color"""
    bl_idname = "wm.y_bake_channel_to_vcol"
    bl_label = "Bake channel to vertex color"
    bl_options = {'REGISTER', 'UNDO'}

    all_materials : BoolProperty(
        name = 'Bake All Materials',
        description = 'Bake all materials with ucupaint nodes rather than just the active one',
        default = False
    )

    vcol_name : StringProperty(
        name = 'Target Vertex Color Name', 
        description = "Target vertex color name, it will create one if it doesn't exist",
        default = ''
    )
    
    add_emission : BoolProperty(
        name = 'Add Emission', 
        description = 'Add the result with Emission Channel', 
        default = False
    )

    emission_multiplier : FloatProperty(
        name = 'Emission Multiplier',
        description = 'Emission multiplier so the emission can be more visible on the result',
        default=1.0, min=0.0
    )

    force_first_index : BoolProperty(
        name = 'Force First Index', 
        description = "Force target vertex color to be first on the vertex colors list (useful for exporting)",
        default = True
    )

    include_alpha : BoolProperty(
        name = 'Include Alpha',
        description = "Bake channel alpha to result (need channel enable alpha)",
        default = False
    )

    bake_to_alpha_only : BoolProperty(
        name = 'Bake To Alpha Only',
        description = "Bake value into the alpha",
        default = False
    )

    @classmethod
    def poll(cls, context):
        return get_active_ypaint_node() and context.object.type == 'MESH'
    
    @classmethod
    def description(self, context, properties):
        return get_operator_description(self)

    def invoke(self, context, event):
        self.invoke_operator(context)

        node = get_active_ypaint_node()
        yp = node.node_tree.yp
        channel = yp.channels[yp.active_channel_index]

        self.vcol_name = 'Baked ' + channel.name

        # Add emission will only be available if it's on Color channel
        self.show_emission_option = False
        if channel.name == 'Color':
            for ch in yp.channels:
                if ch.name == 'Emission':
                    self.show_emission_option = True

        # Only the 'RGB' type has alpha data
        self.show_include_alpha_option = False
        if channel.type == 'RGB':
            self.show_include_alpha_option = True

        # The type 'VALUE' can optionally be directly into the alpha channel
        self.show_bake_to_alpha_only_option = False
        if channel.type == 'VALUE':
            self.show_bake_to_alpha_only_option = True

        if get_user_preferences().skip_property_popups and not event.shift:
            return self.execute(context)

        return context.window_manager.invoke_props_dialog(self, width=320)

    def check(self, context):
        return True

    def draw(self, context):
        row = split_layout(self.layout, 0.4)
        col = row.column(align=True)

        col.label(text='Target Vertex Color:')
        if self.show_emission_option:
            col.label(text='Add Emission:')
            col.label(text='Emission Multiplier:')
        if self.show_include_alpha_option:
            col.label(text='Include Alpha:')
        if self.show_bake_to_alpha_only_option:
            col.label(text='Bake to Alpha:')

        if not is_bl_equal(3, 2):
            col.label(text='Force First Index:')

        col = row.column(align=True)

        col.prop(self, 'vcol_name', text='')
        if self.show_emission_option:
            col.prop(self, 'add_emission', text='')
            col.prop(self, 'emission_multiplier', text='')
        if self.show_include_alpha_option:
            col.prop(self, 'include_alpha', text='')
        if self.show_bake_to_alpha_only_option:
            col.prop(self, 'bake_to_alpha_only', text='')

        if not is_bl_equal(3, 2):
            col.prop(self, 'force_first_index', text='')

    def execute(self, context):
        if not self.is_cycles_exist(context): return {'CANCELLED'}

        if not is_bl_newer_than(2, 92):
            self.report({'ERROR'}, "You need at least Blender 2.92 to use this feature!")
            return {'CANCELLED'}

        mat = get_active_material()
        node = get_active_ypaint_node()
        yp = node.node_tree.yp
        channel = yp.channels[yp.active_channel_index]
        channel_name = channel.name

        book = remember_before_bake(yp)

        if self.all_materials:
            mats = get_all_materials_with_yp_nodes()
        else: mats = [mat]

        for mat in mats:
            for node in mat.node_tree.nodes:
                if node.type != 'GROUP' or not node.node_tree or not node.node_tree.yp.is_ypaint_node: continue
                tree = node.node_tree
                yp = tree.yp
                channel = yp.channels.get(channel_name)
                if not channel: continue

                # Get all objects using material
                objs = []
                meshes = []
                for ob in get_scene_objects():
                    if ob.type != 'MESH': continue
                    if is_bl_newer_than(2, 80) and ob.hide_viewport: continue
                    #if not in_renderable_layer_collection(ob): continue
                    if len(ob.data.polygons) == 0: continue
                    for i, m in enumerate(ob.data.materials):
                        if m == mat:
                            ob.active_material_index = i
                            if ob not in objs and ob.data not in meshes:
                                objs.append(ob)
                                meshes.append(ob.data)

                if not objs: continue

                set_active_object(objs[0])

                # Check vertex color
                for ob in objs:
                    vcols = get_vertex_colors(ob)
                    vcol = vcols.get(self.vcol_name)

                    # Set index to first so new vcol will copy their value
                    if len(vcols) > 0:
                        first_vcol = vcols[0]
                        set_active_vertex_color(ob, first_vcol)

                    if not vcol:
                        try: 
                            vcol = new_vertex_color(ob, self.vcol_name)
                        except Exception as e: print(e)

                    # Get newly created vcol name
                    vcol_name = vcol.name

                    # NOTE: Because of api changes, vertex color shift doesn't work with Blender 3.2
                    if self.force_first_index and not is_bl_equal(3, 2):
                        move_vcol(ob, get_vcol_index(ob, vcol.name), 0)

                    # Get the newly created vcol to avoid pointer error
                    vcol = vcols.get(vcol_name)
                    set_active_vertex_color(ob, vcol)

                # Multi-material setup
                ori_mat_ids = {}
                for ob in objs:

                    # Need to assign all polygon to active material if there are multiple materials
                    ori_mat_ids[ob.name] = []

                    if len(ob.data.materials) > 1:

                        active_mat_id = [i for i, m in enumerate(ob.data.materials) if m == mat][0]
                        for p in ob.data.polygons:

                            # Set active mat
                            ori_mat_ids[ob.name].append(p.material_index)
                            p.material_index = active_mat_id

                # Prepare bake settings
                prepare_bake_settings(
                    book, objs, yp, disable_problematic_modifiers=True,
                    bake_device=self.bake_device, bake_target='VERTEX_COLORS'
                )

                # Get extra channel
                extra_channel = None
                if self.show_emission_option and self.add_emission:
                    extra_channel = yp.channels.get('Emission')

                # Bake channel
                bake_to_vcol(
                    mat, node, channel, objs, extra_channel, self.emission_multiplier,
                    self.include_alpha or self.bake_to_alpha_only, self.vcol_name
                )

                for ob in objs:
                    # Recover material index
                    if ori_mat_ids[ob.name]:
                        for i, p in enumerate(ob.data.polygons):
                            if ori_mat_ids[ob.name][i] != p.material_index:
                                p.material_index = ori_mat_ids[ob.name][i]

        # Recover bake settings
        recover_bake_settings(book, yp)

        return {'FINISHED'}

class YDeleteBakedChannelImages(bpy.types.Operator):
    bl_idname = "wm.y_delete_baked_channel_images"
    bl_label = "Delete All Baked Channel Images"
    bl_description = "Delete all baked channel images"
    bl_options = {'UNDO'}

    also_del_vcol : BoolProperty(
        name = "Also delete the vertex color",
        default = False
    )

    @classmethod
    def poll(cls, context):
        return get_active_ypaint_node() and context.object.type == 'MESH'

    @classmethod
    def description(self, context, properties):
        return get_operator_description(self)

    def invoke(self, context, event):
        node = get_active_ypaint_node()
        tree = node.node_tree
        yp = tree.yp

        self.any_channel_use_baked_vcol = False

        if not get_user_preferences().skip_property_popups or event.shift:
            for ch in yp.channels:
                baked_vcol_node = tree.nodes.get(ch.baked_vcol)
                self.baked_vcol_name = baked_vcol_node.attribute_name if baked_vcol_node else ''
                if self.baked_vcol_name != '':
                    self.any_channel_use_baked_vcol = True
                    return context.window_manager.invoke_props_dialog(self, width=320)

        self.also_del_vcol = False
        return self.execute(context)

    def draw(self, context):
        if self.any_channel_use_baked_vcol:
            title="Also remove baked vertex colors"
            self.layout.prop(self, 'also_del_vcol', text=title)

    def execute(self, context):
        node = get_active_ypaint_node()
        tree = node.node_tree
        yp = tree.yp
        mat = get_active_material()

        # Set bake to false first
        if yp.use_baked:
            yp.use_baked = False

        # Remove baked nodes
        for root_ch in yp.channels:

            # Delete baked vertex color
            if self.also_del_vcol:
                for ob in get_all_objects_with_same_materials(mat):
                    vcols = get_vertex_colors(ob)
                    if len(vcols) == 0: continue
                    baked_vcol_node = tree.nodes.get(root_ch.baked_vcol)
                    if baked_vcol_node:
                        vcol = vcols.get(baked_vcol_node.attribute_name)
                        if vcol:
                            vcols.remove(vcol)

            remove_node(tree, root_ch, 'baked')
            remove_node(tree, root_ch, 'baked_vcol')

            if root_ch.type == 'NORMAL':
                remove_node(tree, root_ch, 'baked_disp')
                remove_node(tree, root_ch, 'baked_vdisp')
                remove_node(tree, root_ch, 'baked_normal_overlay')
                remove_node(tree, root_ch, 'baked_normal_prep')
                remove_node(tree, root_ch, 'baked_normal')
                remove_node(tree, root_ch, 'end_max_height')

        # Reconnect
        reconnect_yp_nodes(tree)
        rearrange_yp_nodes(tree)

        return {'FINISHED'}

def update_bake_channel_uv_map(self, context):
    if not UDIM.is_udim_supported(): return

    if get_user_preferences().enable_auto_udim_detection:
        mat = get_active_material()
        objs = get_all_objects_with_same_materials(mat)
        self.use_udim = UDIM.is_uvmap_udim(objs, self.uv_map)

def bake_vcol_channel_items(self, context):
    node = get_active_ypaint_node()
    yp = node.node_tree.yp

    items = []
    # Default option to do nothing
    items.append(('Do Nothing', 'Do Nothing', '', '', 0))
    items.append(('Sort By Channel Order', 'Sort By Channel Order', '', '', 1))

    for i, ch in enumerate(yp.channels):
        if not ch.enable_bake_to_vcol: continue
        # Add two spaces to prevent text from being translated
        text_ch_name = ch.name + '  '
        # Index plus one, minus one when read
        icon_name = lib.channel_custom_icon_dict[ch.type]
        items.append((str(i + 2), text_ch_name, '', lib.get_icon(icon_name), i + 2))

    return items

class YBakeChannels(bpy.types.Operator, BaseBakeOperator):
    """Bake Channels to Image(s)"""
    bl_idname = "wm.y_bake_channels"
    bl_label = "Bake channels to Image"
    bl_options = {'REGISTER', 'UNDO'}

    uv_map : StringProperty(default='', update=update_bake_channel_uv_map)
    uv_map_coll : CollectionProperty(type=bpy.types.PropertyGroup)

    interpolation : EnumProperty(
        name = 'Image Interpolation Type',
        description = 'Image interpolation type',
        items = interpolation_type_items,
        default = 'Linear'
    )

    #hdr : BoolProperty(name='32 bit Float', default=False)

    only_active_channel : BoolProperty(
        name = 'Only Bake Active Channel',
        description = 'Only bake active channel',
        default = False
    )

    fxaa : BoolProperty(
        name = 'Use FXAA', 
        description = "Use FXAA to baked images (doesn't work with float/non clamped images)",
        default = True
    )

    aa_level : IntProperty(
        name = 'Anti Aliasing Level',
        description = 'Super Sample Anti Aliasing Level (1=off)',
        default=1, min=1, max=2
    )

    denoise : BoolProperty(
        name = 'Use Denoise', 
        description = "Use Denoise on baked images",
        default = False
    )

    force_bake_all_polygons : BoolProperty(
        name = 'Force Bake all Polygons',
        description = 'Force bake all polygons, useful if material is not using direct polygon (ex: solidify material)',
        default = False
    )

    enable_bake_as_vcol : BoolProperty(
        name = 'Enable Bake As VCol',
        description = 'Has any channel enabled Bake As Vertex Color',
        default = False
    )

    vcol_force_first_ch_idx : EnumProperty(
        name = 'Force First Vertex Color Channel',
        description = 'Force the first channel after baking the Vertex Color',
        items = bake_vcol_channel_items
    )

    vcol_force_first_ch_idx_bool : BoolProperty(
        name = 'Force First Vertex Color Channel',
        description = 'Force the first channel after baking the Vertex Color',
        default = False
    )

    use_udim : BoolProperty(
        name = 'Use UDIM Tiles',
        description = 'Use UDIM Tiles',
        default = False
    )

    use_float_for_normal : BoolProperty(
        name = 'Use Float for Normal',
        description = 'Use float image for baked normal',
        default = False
    )

    use_float_for_displacement : BoolProperty(
        name = 'Use Float for Displacement',
        description = 'Use float image for baked displacement',
        default = False
    )

    use_dithering : BoolProperty(
        name = 'Use Dithering',
        description = 'Use dithering for less banding color',
        default = False
    )

    dither_intensity : FloatProperty(
        name = 'Dither Intensity',
        description = 'Amount of dithering noise added to the rendered image to break up banding',
        default=1.0, min=0.0, max=2.0, subtype='FACTOR'
    )
    
    bake_disabled_layers : BoolProperty(
        name = 'Bake Disabled Layers',  
        description = 'Take disabled layers into account when baking',
        default = False
    )

    @classmethod
    def poll(cls, context):
        return get_active_ypaint_node() and context.object.type == 'MESH'

    def invoke(self, context, event):
        self.invoke_operator(context)

        node = get_active_ypaint_node()
        yp = node.node_tree.yp
        obj = self.obj = context.object
        scene = context.scene
        ypup = get_user_preferences()

        # Use active uv layer name by default
        uv_layers = get_uv_layers(obj)

        # Use active uv layer name by default
        if obj.type == 'MESH' and len(uv_layers) > 0:
            if uv_layers.get(yp.baked_uv_name):
                self.uv_map = yp.baked_uv_name
            else:
                active_name = uv_layers.active.name
                if active_name == TEMP_UV:
                    self.uv_map = yp.layers[yp.active_layer_index].uv_name
                else: self.uv_map = uv_layers.active.name

            # UV Map collections update
            self.uv_map_coll.clear()
            for uv in uv_layers:
                if not uv.name.startswith(TEMP_UV):
                    self.uv_map_coll.add().name = uv.name

        # List of channels that will be baked
        if self.only_active_channel and yp.active_channel_index < len(yp.channels):
            active_ch = yp.channels[yp.active_channel_index]
            self.channels = [active_ch]

            # Add alpha/color channel pair
            color_ch, alpha_ch = get_color_alpha_ch_pairs(yp)
            if active_ch == color_ch:
                self.channels.append(alpha_ch)
            elif active_ch == alpha_ch:
                self.channels.append(color_ch)

        else: self.channels = yp.channels

        self.enable_bake_as_vcol = False
        if len(self.channels) > 0:
            bi = None
            for ch in self.channels:
                baked = node.node_tree.nodes.get(ch.baked)
                if baked and baked.image:
                    if baked.image.y_bake_info.is_baked:
                        bi = baked.image.y_bake_info
                    self.width = baked.image.size[0] if baked.image.size[0] != 0 else ypup.default_new_image_size
                    self.height = baked.image.size[1] if baked.image.size[1] != 0 else ypup.default_new_image_size
                    break
            
            for ch in self.channels:
                if ch.enable_bake_to_vcol:
                    self.enable_bake_as_vcol = True
                    break

            # Set some attributes from bake info
            if bi:
                for attr in dir(bi):
                    if attr in {'other_objects', 'selected_objects'}: continue
                    if attr.startswith('__'): continue
                    if attr.startswith('bl_'): continue
                    if attr in {'rna_type'}: continue
                    #if attr in dir(self):
                    try: setattr(self, attr, getattr(bi, attr))
                    except: pass

        if self.vcol_force_first_ch_idx == '':
            self.vcol_force_first_ch_idx = 'Do Nothing'

        if get_user_preferences().skip_property_popups and not event.shift:
            return self.execute(context)

        return context.window_manager.invoke_props_dialog(self, width=320)

    def check(self, context):
        self.check_operator(context)
        return True

    def draw(self, context):
        node = get_active_ypaint_node()
        yp = node.node_tree.yp
        height_root_ch = get_root_height_channel(yp)
        
        obj = context.object
        mat = obj.active_material

        row = split_layout(self.layout, 0.4)
        col = row.column() #align=True)

        ccol = col.column(align=True)
        ccol.label(text='')
        if self.use_custom_resolution == False:
            ccol.label(text='Resolution:')
        if self.use_custom_resolution == True:
            ccol.label(text='Width:')
            ccol.label(text='Height:')

        ccol.separator()
        ccol.label(text='Samples:')
        ccol.label(text='AA Level:')

        if is_bl_newer_than(3, 1):
            ccol.separator()
        ccol.label(text='Margin:')

        if height_root_ch:
            ccol.separator()
            ccol.label(text='Use 32-bit Float:')

        col.separator()

        if is_bl_newer_than(2, 80):
            col.label(text='Bake Device:')
        col.label(text='Interpolation:')
        col.label(text='UV Map:')

        ccol = col.column(align=True)

        # NOTE: Because of api changes, vertex color shift doesn't work with Blender 3.2
        active_channel = None
        if self.only_active_channel and not is_bl_equal(3, 2):
            active_channel = self.channels[0]
            if active_channel.enable_bake_to_vcol:
                ccol.separator()
                ccol.label(text='')
        elif self.enable_bake_as_vcol and not is_bl_equal(3, 2):
            ccol.separator()
            ccol.label(text='Force First Vcol:')

        col = row.column()

        col.prop(self, 'use_custom_resolution')
        crow = col.row(align=True)
        ccol = col.column(align=True)

        if self.use_custom_resolution == False:
            crow.prop(self, 'image_resolution', expand= True,)
        elif self.use_custom_resolution == True:
            ccol.prop(self, 'width', text='')
            ccol.prop(self, 'height', text='')

        ccol.separator()
        ccol.prop(self, 'samples', text='')
        ccol.prop(self, 'aa_level', text='')

        if is_bl_newer_than(3, 1):
            ccol.separator()
            split = split_layout(ccol, 0.4, align=True)
            split.prop(self, 'margin', text='')
            split.prop(self, 'margin_type', text='')
        else:
            ccol.prop(self, 'margin', text='')

        if height_root_ch:
            ccol.separator()
            splits = split_layout(ccol, 0.4)
            splits.prop(self, 'use_float_for_normal', emboss=True, text='Normal') #, icon='IMAGE_DATA')
            splits.prop(self, 'use_float_for_displacement', emboss=True, text='Displacement') #, icon='IMAGE_DATA')

        col.separator()

        if is_bl_newer_than(2, 80):
            col.prop(self, 'bake_device', text='')
        col.prop(self, 'interpolation', text='')
        col.prop_search(self, "uv_map", self, "uv_map_coll", text='', icon='GROUP_UVS')

        ccol = col.column(align=True)

        # NOTE: Because of api changes, vertex color shift doesn't work with Blender 3.2
        if active_channel and active_channel.enable_bake_to_vcol:
            ccol.separator()
            ccol.prop(self, 'vcol_force_first_ch_idx_bool', text='Force First Vcol')
        elif self.enable_bake_as_vcol and not is_bl_equal(3, 2):
            ccol.separator()
            ccol.prop(self, 'vcol_force_first_ch_idx', text='')

        ccol.separator()

        if UDIM.is_udim_supported():
            ccol.prop(self, 'use_udim')
        ccol.prop(self, 'fxaa', text='Use FXAA')
        if is_bl_newer_than(2, 81):
            ccol.prop(self, 'denoise', text='Use Denoise')

        any_color_channel = any([c for c in self.channels if c.type == 'RGB' and c.colorspace == 'SRGB' and c.use_clamp])
        if any_color_channel:
            if not self.use_dithering:
                ccol.prop(self, 'use_dithering', text='Use Dithering')
            if self.use_dithering:
                row = split_layout(ccol, 0.55)
                row.prop(self, 'use_dithering', text='Use Dithering')
                row.prop(self, 'dither_intensity', text='')

        ccol.prop(self, 'force_bake_all_polygons')
        ccol.prop(self, 'bake_disabled_layers')

    def execute(self, context):
        if not self.is_cycles_exist(context): return {'CANCELLED'}

        T = time.time()

        node = get_active_ypaint_node()
        tree = node.node_tree
        yp = tree.yp
        scene = context.scene
        obj = context.object
        mat = obj.active_material

        if is_bl_newer_than(2, 80) and (obj.hide_viewport or obj.hide_render):
            self.report({'ERROR'}, "Please unhide render and viewport of the active object!")
            return {'CANCELLED'}

        if not is_bl_newer_than(2, 80) and obj.hide_render:
            self.report({'ERROR'}, "Please unhide render of the active object!")
            return {'CANCELLED'}

        # Get all objects using material
        objs = [obj]
        meshes = [obj.data]
        if mat.users > 1:
            # Emptying the lists again in case active object is problematic
            objs = []
            meshes = []
            for ob in get_scene_objects():
                if ob.type != 'MESH': continue
                if is_bl_newer_than(2, 80) and ob.hide_viewport: continue
                if ob.hide_render: continue
                #if not in_renderable_layer_collection(ob): continue
                if len(get_uv_layers(ob)) == 0: continue
                if len(ob.data.polygons) == 0: continue
                for i, m in enumerate(ob.data.materials):
                    if m == mat:
                        ob.active_material_index = i
                        if ob not in objs and ob.data not in meshes:
                            objs.append(ob)
                            meshes.append(ob.data)

        if not objs:
            self.report({'ERROR'}, "No valid objects to bake!")
            return {'CANCELLED'}

        # UV data should be accessible when there's multiple materials in single object, so object mode is necessary
        ori_edit_mode = False
        if len(obj.data.materials) > 1 and obj.mode == 'EDIT':
            bpy.ops.object.mode_set(mode='OBJECT')
            ori_edit_mode = True

        book = remember_before_bake(yp)

        height_ch = get_root_height_channel(yp)

        tangent_sign_calculation = False
        if BL28_HACK and height_ch and is_bl_newer_than(2, 80) and not is_bl_newer_than(3) and obj in objs:

            if len(yp.uvs) > MAX_VERTEX_DATA - len(get_vertex_colors(obj)):
                self.report({'WARNING'}, "Maximum vertex colors reached! Need at least " + str(len(yp.uvs)) + " vertex color(s) to bake proper normal!")
            else:
                print('INFO: Calculating tangent sign before bake...')
                tangent_sign_calculation = True

            if tangent_sign_calculation:
                # Update tangent sign vertex color
                for uv in yp.uvs:
                    tangent_process = tree.nodes.get(uv.tangent_process)
                    if tangent_process:
                        tangent_process.inputs['Backface Always Up'].default_value = 1.0 if yp.enable_backface_always_up else 0.0
                        #tangent_process.inputs['Blender 2.8 Cycles Hack'].default_value = 1.0
                        tansign = tangent_process.node_tree.nodes.get('_tangent_sign')
                        vcol = refresh_tangent_sign_vcol(obj, uv.name)
                        if vcol: tansign.attribute_name = vcol.name

        # Disable use baked first
        if yp.use_baked:
            yp.use_baked = False

        # Multi materials setup
        ori_mat_ids = {}
        ori_loop_locs = {}
        for ob in objs:

            # Need to assign all polygon to active material if there are multiple materials
            ori_mat_ids[ob.name] = []
            ori_loop_locs[ob.name] = []

            if len(ob.data.materials) > 1:

                # Get uv map
                uv_layers = get_uv_layers(ob)
                uvl = uv_layers.get(self.uv_map)

                active_mat_id = [i for i, m in enumerate(ob.data.materials) if m == mat][0]
                for p in ob.data.polygons:

                    # Set uv location to (0,0) if not using current material
                    if uvl and not self.force_bake_all_polygons:
                        uv_locs = []
                        for li in p.loop_indices:
                            uv_locs.append(uvl.data[li].uv.copy())
                            if p.material_index != active_mat_id:
                                uvl.data[li].uv = Vector((0.0, 0.0))

                        ori_loop_locs[ob.name].append(uv_locs)

                    # Set active mat
                    ori_mat_ids[ob.name].append(p.material_index)
                    p.material_index = active_mat_id

        # Check if any objects use geometry nodes to output uv
        any_uv_geonodes = False
        for o in objs:
            if any(get_output_uv_names_from_geometry_nodes(o)):
                any_uv_geonodes = True

        # Join objects if the number of objects is higher than one 
        # or if there are uvs generated by geometry nodes
        temp_objs = []
        ori_objs = []
        if (len(objs) > 1 or any_uv_geonodes) and not is_join_objects_problematic(yp, mat):
            ori_objs = objs
            objs = temp_objs = [get_merged_mesh_objects(scene, objs)]
            
        # AA setup
        #if self.aa_level > 1:
        margin = self.margin * self.aa_level
        width = self.width * self.aa_level
        height = self.height * self.aa_level

        # Prepare bake settings
        prepare_bake_settings(
            book, objs, yp, self.samples, margin, self.uv_map, disable_problematic_modifiers=True, 
            bake_device=self.bake_device, margin_type=self.margin_type
        )

        # Get tilenums
        tilenums = UDIM.get_tile_numbers(objs, self.uv_map) if self.use_udim else [1001]

        # Enable disabled layers if needed
        disabled_layers = []
        if self.bake_disabled_layers:
            disabled_layers = [layer for layer in yp.layers if not layer.enable]
            for layer in disabled_layers:
                layer.enable = True 

        # Get color and alpha channel
        color_ch, alpha_ch = get_color_alpha_ch_pairs(yp)

        # Bake channels
        baked_exists = []
        for ch in self.channels:

            # Remove baked node if alpha channel will be combined to color channel
            if alpha_ch == ch and alpha_ch.alpha_combine_to_baked_color:
                remove_node(tree, alpha_ch, 'baked')
                ch.no_layer_using = False
                continue

            # Check if baked node exists
            baked = tree.nodes.get(ch.baked)
            if baked: baked_exists.append(True)
            else: baked_exists.append(False)

            ch.no_layer_using = not is_any_layer_using_channel(ch, node)
            if not ch.no_layer_using:
                use_hdr = not ch.use_clamp or (self.use_dithering and ch.type == 'RGB' and ch.colorspace == 'SRGB')
                bake_channel(
                    self.uv_map, mat, node, ch, width, height, use_hdr=use_hdr, force_use_udim=self.use_udim, 
                    tilenums=tilenums, interpolation=self.interpolation, 
                    use_float_for_displacement=self.use_float_for_displacement, 
                    use_float_for_normal=self.use_float_for_normal
                )

        # Process baked images
        baked_images = []
        for i, ch in enumerate(self.channels):

            baked = tree.nodes.get(ch.baked)
            if baked and baked.image:

                # Only expand baked data when baked is just created
                if not baked_exists[i]:
                    ch.expand_baked_data = True

                alpha_enabled = ch.enable_alpha or (ch == color_ch and alpha_ch.alpha_combine_to_baked_color)

                # Dithering
                if ch.type == 'RGB' and ch.colorspace == 'SRGB' and self.use_dithering and ch.use_clamp:
                    dither_image(baked.image, dither_intensity=self.dither_intensity, alpha_aware=alpha_enabled)

                # Denoise
                if self.denoise and is_bl_newer_than(2, 81) and ch.type != 'NORMAL':
                    denoise_image(baked.image)

                # AA process
                if self.aa_level > 1:
                    resize_image(
                        baked.image, self.width, self.height, 
                        baked.image.colorspace_settings.name,
                        alpha_aware=alpha_enabled, bake_device=self.bake_device
                    )

                # FXAA doesn't work with hdr image
                if self.fxaa and ch.use_clamp:
                    fxaa_image(baked.image, alpha_enabled, bake_device=self.bake_device)

                baked_images.append(baked.image)

            if ch.type == 'NORMAL':

                baked_disp = tree.nodes.get(ch.baked_disp)
                if baked_disp and baked_disp.image:

                    # Denoise
                    if self.denoise and is_bl_newer_than(2, 81):
                        denoise_image(baked_disp.image)

                    # AA process
                    if self.aa_level > 1:
                        resize_image(
                            baked_disp.image, self.width, self.height, 
                            baked.image.colorspace_settings.name,
                            alpha_aware=alpha_enabled, bake_device=self.bake_device
                        )

                    # FXAA
                    if self.fxaa and not baked_disp.image.is_float:
                        fxaa_image(baked_disp.image, alpha_enabled, bake_device=self.bake_device)

                    baked_images.append(baked_disp.image)

                baked_normal_overlay = tree.nodes.get(ch.baked_normal_overlay)
                if baked_normal_overlay and baked_normal_overlay.image:

                    # AA process
                    if self.aa_level > 1:
                        resize_image(
                            baked_normal_overlay.image, self.width, self.height, 
                            baked.image.colorspace_settings.name,
                            alpha_aware=alpha_enabled, bake_device=self.bake_device
                        )
                    # FXAA
                    if self.fxaa:
                        fxaa_image(baked_normal_overlay.image, alpha_enabled, bake_device=self.bake_device)

                    baked_images.append(baked_normal_overlay.image)

                baked_vdisp = tree.nodes.get(ch.baked_vdisp)
                if baked_vdisp and baked_vdisp.image:

                    # AA process
                    if self.aa_level > 1:
                        resize_image(
                            baked_vdisp.image, self.width, self.height, 
                            baked.image.colorspace_settings.name,
                            alpha_aware=alpha_enabled, bake_device=self.bake_device
                        )

                    baked_images.append(baked_vdisp.image)

        # Set bake info to baked images
        for img in baked_images:
            bi = img.y_bake_info
            for attr in dir(bi):
                #if attr in dir(self):
                if attr.startswith('__'): continue
                if attr.startswith('bl_'): continue
                if attr in {'rna_type'}: continue
                try: setattr(bi, attr, getattr(self, attr))
                except: pass
            bi.is_baked = True
            bi.is_baked_channel = True

        # Process custom bake target images
        # Can only happen when only active channel is off since require all baked images to have the same resolution
        if not self.only_active_channel:
            for bt in yp.bake_targets:
                print("INFO: Processing custom bake target '" + bt.name + "'...")
                bt_node = tree.nodes.get(bt.image_node)
                btimg = bt_node.image if bt_node and bt_node.image else None 
                
                old_img = None
                filepath = ''
                if btimg and (
                        btimg.size[0] != self.width or btimg.size[1] != self.height or
                        (btimg.source == 'TILED' and not self.use_udim) or
                        (btimg.source != 'TILED' and self.use_udim) 
                        ):
                    old_img = btimg
                    btimg = None
                    if (old_img.source == 'TILED' and self.use_udim) or (old_img.source != 'TILED' and not self.use_udim):
                        filepath = old_img.filepath

                # Get default colors
                color = []
                for letter in rgba_letters:
                    btc = getattr(bt, letter)
                    ch = [c for c in self.channels if c.name == (getattr(btc, 'channel_name'))]
                    if ch: ch = ch[0]
                    if ch and ch.type == 'NORMAL':
                        if btc.normal_type in {'COMBINED', 'OVERLAY_ONLY'}:
                            # Normal RG default value
                            if btc.subchannel_index in {'0', '1'}:
                                color.append(0.5)
                            else: 
                                # Normal BA default value
                                color.append(1.0)
                        else: 
                            # Displacement default value
                            color.append(0.5)
                    else:
                        color.append(btc.default_value)

                if not btimg:
                    # Set new bake target image
                    if len(tilenums) > 1:
                        btimg = bpy.data.images.new(
                            name=bt.name, width=self.width, height=self.height, 
                            alpha=True, tiled=True, float_buffer=bt.use_float
                        )
                        btimg.colorspace_settings.name = get_noncolor_name()
                        btimg.filepath = filepath

                        # Fill tiles
                        for tilenum in tilenums:
                            UDIM.fill_tile(btimg, tilenum, color, self.width, self.height)

                        UDIM.initial_pack_udim(btimg, color)
                    else:
                        btimg = bpy.data.images.new(
                            name=bt.name, width=self.width, height=self.height,
                            alpha=True, float_buffer=bt.use_float
                        )
                        btimg.colorspace_settings.name = get_noncolor_name()
                        btimg.filepath = filepath
                        btimg.generated_color = color
                else:
                    for tilenum in tilenums:

                        # Swap tile
                        if tilenum != 1001:
                            UDIM.swap_tile(btimg, 1001, tilenum)

                        # Only set image color if image is already found
                        set_image_pixels(btimg, color)

                        # Swap tile again to recover
                        if tilenum != 1001:
                            UDIM.swap_tile(btimg, 1001, tilenum)

                # Copy image channels
                for i, letter in enumerate(rgba_letters):
                    btc = getattr(bt, letter)
                    ch = [c for c in self.channels if c.name == (getattr(btc, 'channel_name'))]
                    if ch:
                        ch = ch[0]

                        # Get image channel
                        subidx = 0
                        if ch.type in {'RGB', 'NORMAL'}:
                            subidx = int(getattr(btc, 'subchannel_index'))

                        # Get baked node
                        baked = None
                        if ch.type == 'NORMAL' and btc.normal_type == 'OVERLAY_ONLY':
                            baked = tree.nodes.get(ch.baked_normal_overlay)
                        elif ch.type == 'NORMAL' and btc.normal_type == 'DISPLACEMENT':
                            baked = tree.nodes.get(ch.baked_disp)
                            subidx = 0
                        elif ch.type == 'NORMAL' and btc.normal_type == 'VECTOR_DISPLACEMENT':
                            baked = tree.nodes.get(ch.baked_vdisp)
                        else: baked = tree.nodes.get(ch.baked)

                        if baked and baked.image:
                            for tilenum in tilenums:
                                # Swap tile
                                if tilenum != 1001:
                                    UDIM.swap_tile(btimg, 1001, tilenum)
                                    UDIM.swap_tile(baked.image, 1001, tilenum)

                                # Copy pixels
                                copy_image_channel_pixels(
                                    baked.image, btimg, src_idx=subidx,
                                    dest_idx=i, invert_value=btc.invert_value
                                )

                                # Swap tile again to recover
                                if tilenum != 1001:
                                    UDIM.swap_tile(btimg, 1001, tilenum)
                                    UDIM.swap_tile(baked.image, 1001, tilenum)

                # Set bake target image
                if old_img: 
                    replace_image(old_img, btimg)
                else: 
                    bt_node = check_new_node(tree, bt, 'image_node', 'ShaderNodeTexImage')
                    bt_node.image = btimg

        # Set baked uv
        yp.baked_uv_name = self.uv_map

        # Recover bake settings
        recover_bake_settings(book, yp)

        # Recover disabled layers
        if self.bake_disabled_layers:
            for layer in disabled_layers:
                layer.enable = False

        # Return to original objects
        if ori_objs: objs = ori_objs

        for ob in objs:
            # Recover material index
            if ori_mat_ids[ob.name]:
                for i, p in enumerate(ob.data.polygons):
                    if ori_mat_ids[ob.name][i] != p.material_index:
                        p.material_index = ori_mat_ids[ob.name][i]

            if ori_loop_locs[ob.name]:

                # Get uv map
                uv_layers = get_uv_layers(ob)
                uvl = uv_layers.get(self.uv_map)

                # Recover uv locations
                if uvl:
                    for i, p in enumerate(ob.data.polygons):
                        for j, li in enumerate(p.loop_indices):
                            uvl.data[li].uv = ori_loop_locs[ob.name][i][j]

        # Bake vcol
        if is_bl_newer_than(2, 92):
            is_do_nothing = True
            is_sort_by_channel = False
            if self.only_active_channel:
                active_channel = self.channels[0]
                if active_channel.enable_bake_to_vcol and self.vcol_force_first_ch_idx_bool:
                    real_force_first_ch_idx = yp.active_channel_index
                    is_do_nothing = False
            else:
                is_do_nothing = self.vcol_force_first_ch_idx == 'Do Nothing'
                is_sort_by_channel = self.vcol_force_first_ch_idx == 'Sort By Channel Order'
                # check index, prevent crash
                if not (is_do_nothing or is_sort_by_channel) and self.vcol_force_first_ch_idx != '':
                    real_force_first_ch_idx = int(self.vcol_force_first_ch_idx) - 2
                    if real_force_first_ch_idx < len(self.channels) and real_force_first_ch_idx >= 0:
                        target_ch = self.channels[real_force_first_ch_idx]
                        if not (target_ch and target_ch.enable_bake_to_vcol):
                            real_force_first_ch_idx = -1
                    else: real_force_first_ch_idx = -1
                else:
                    real_force_first_ch_idx = -1
            # used to sort by channel
            current_vcol_order = 0
            prepare_bake_settings(
                book, objs, yp, disable_problematic_modifiers=True,
                bake_device=self.bake_device, bake_target='VERTEX_COLORS'
            )
            for ch in self.channels:
                if ch.enable_bake_to_vcol and ch.type != 'NORMAL':
                    # Check vertex color
                    for ob in objs:
                        vcols = get_vertex_colors(ob)
                        vcol = vcols.get(ch.bake_to_vcol_name)

                        # Set index to first so new vcol will copy their value
                        if len(vcols) > 0:
                            first_vcol = vcols[0]
                            set_active_vertex_color(ob, first_vcol)

                        if not vcol:
                            try: 
                                vcol = new_vertex_color(ob, ch.bake_to_vcol_name)
                            except Exception as e: print(e)

                        # Get newly created vcol name
                        vcol_name = vcol.name

                        # NOTE: Because of api changes, vertex color shift doesn't work with Blender 3.2
                        if not is_bl_equal(3, 2) and not is_do_nothing:
                            if is_sort_by_channel or (real_force_first_ch_idx >= 0 and yp.channels[real_force_first_ch_idx] == ch):
                                move_vcol(ob, get_vcol_index(ob, vcol.name), current_vcol_order)

                        # Get the newly created vcol to avoid pointer error
                        vcol = vcols.get(vcol_name)
                        set_active_vertex_color(ob, vcol)
                    bake_to_vcol(mat, node, ch, objs, None, 1, ch.bake_to_vcol_alpha or ch.enable_alpha, ch.bake_to_vcol_name)
                    baked = tree.nodes.get(ch.baked_vcol)
                    if not baked or not is_root_ch_prop_node_unique(ch, 'baked_vcol'):
                        baked = new_node(tree, ch, 'baked_vcol', get_vcol_bl_idname(), 'Baked Vcol ' + ch.name)
                        # Set channel to use baked vertex color only when baked_vcol is just created
                        ch.use_baked_vcol = True

                    set_source_vcol_name(baked, ch.bake_to_vcol_name)
                    for ob in objs:
                        # Recover material index
                        if ori_mat_ids[ob.name]:
                            for i, p in enumerate(ob.data.polygons):
                                if ori_mat_ids[ob.name][i] != p.material_index:
                                    p.material_index = ori_mat_ids[ob.name][i]
                    if is_sort_by_channel:
                        current_vcol_order += 1
                else:
                    # If has baked vcol node, remove it
                    baked = tree.nodes.get(ch.baked_vcol)
                    if baked:
                        simple_remove_node(tree, baked)

            # Sort vcols by channel order
            # Recover bake settings
            recover_bake_settings(book, yp)
        # Use bake results
        yp.halt_update = True
        yp.use_baked = True
        yp.halt_update = False

        # Check subdiv Setup
        if height_ch:
            check_subdiv_setup(height_ch)

        # Update global uv
        check_uv_nodes(yp)

        # Check start and end nodes
        check_start_end_root_ch_nodes(tree)

        # Recover hack
        if BL28_HACK and height_ch and tangent_sign_calculation and is_bl_newer_than(2, 80) and not is_bl_newer_than(3):
            print('INFO: Recovering tangent sign after bake...')
            # Refresh tangent sign hacks
            update_enable_tangent_sign_hacks(yp, context)

        # Rearrange
        reconnect_yp_nodes(tree)
        rearrange_yp_nodes(tree)

        # Revert back to edit mode
        if ori_edit_mode:
            bpy.ops.object.mode_set(mode='EDIT')
        
        # Refresh active channel index
        yp.active_channel_index = yp.active_channel_index

        # Update UI
        ypui = context.window_manager.ypui
        ypui.need_update = True

        # If bake target ui is visible, refresh bake target index to show up the image result
        if len(yp.bake_targets) > 0:
            if ypui.show_bake_targets:
                yp.active_bake_target_index = yp.active_bake_target_index

        # Update baked outside nodes
        update_enable_baked_outside(yp, context)

        # Remove temporary objects
        if temp_objs:
            for o in temp_objs:
                remove_mesh_obj(o)

        print('INFO:', tree.name, 'channels are baked in', '{:0.2f}'.format(time.time() - T), 'seconds!')

        return {'FINISHED'}

def merge_channel_items(self, context):
    node = get_active_ypaint_node()
    yp = node.node_tree.yp
    layer = yp.layers[yp.active_layer_index]
    #layer = self.layer
    #neighbor_layer = self.neighbor_layer

    items = []

    counter = 0
    for i, ch in enumerate(yp.channels):
        if not layer.channels[i].enable: continue
        icon_name = lib.channel_custom_icon_dict[ch.type]
        items.append((str(i), ch.name, '', lib.get_icon(icon_name), counter))
        counter += 1

    return items

def remember_and_disable_layer_modifiers_and_transforms(layer, disable_masks=False):
    yp = layer.id_data.yp

    oris = {}

    oris['mods'] = []
    for mod in layer.modifiers:
        oris['mods'].append(mod.enable)
        mod.enable = False

    oris['ch_mods'] = {}
    oris['ch_trans_bumps'] = []
    oris['ch_trans_aos'] = []
    oris['ch_trans_ramps'] = []

    for i, c in enumerate(layer.channels):
        rch = yp.channels[i]
        ch_name = rch.name

        oris['ch_mods'][ch_name] = []
        for mod in c.modifiers:
            oris['ch_mods'][ch_name].append(mod.enable)
            mod.enable = False

        oris['ch_trans_bumps'].append(c.enable_transition_bump)
        oris['ch_trans_aos'].append(c.enable_transition_ao)
        oris['ch_trans_ramps'].append(c.enable_transition_ramp)

        if rch.type == 'NORMAL':
            if c.enable_transition_bump:
                c.enable_transition_bump = False
        else:
            if c.enable_transition_ao:
                c.enable_transition_ao = False
            if c.enable_transition_ramp:
                c.enable_transition_ramp = False

    oris['masks'] = []
    for i, m in enumerate(layer.masks):
        oris['masks'].append(m.enable)
        if m.enable and disable_masks:
            m.enable = False

    return oris

def recover_layer_modifiers_and_transforms(layer, oris):
    yp = layer.id_data.yp

    # Recover original layer modifiers
    for i, mod in enumerate(layer.modifiers):
        mod.enable = oris['mods'][i]

    for i, c in enumerate(layer.channels):
        rch = yp.channels[i]
        ch_name = rch.name

        # Recover original channel modifiers
        for j, mod in enumerate(c.modifiers):
            mod.enable = oris['ch_mods'][ch_name][j]

        # Recover original channel transition effects
        if rch.type == 'NORMAL':
            if oris['ch_trans_bumps'][i]:
                c.enable_transition_bump = oris['ch_trans_bumps'][i]
        else:
            if oris['ch_trans_aos'][i]:
                c.enable_transition_ao = oris['ch_trans_aos'][i]
            if oris['ch_trans_ramps'][i]:
                c.enable_transition_ramp = oris['ch_trans_ramps'][i]

    for i, m in enumerate(layer.masks):
        if oris['masks'][i] != m.enable:
            m.enable = oris['masks'][i]

def remove_layer_modifiers_and_transforms(layer):
    yp = layer.id_data.yp

    # Remove layer modifiers
    for i, mod in reversed(list(enumerate(layer.modifiers))):

        # Delete the nodes
        mod_tree = get_mod_tree(layer)
        Modifier.delete_modifier_nodes(mod_tree, mod)
        layer.modifiers.remove(i)

    for i, c in enumerate(layer.channels):
        rch = yp.channels[i]
        ch_name = rch.name

        # Remove channel modifiers
        for j, mod in reversed(list(enumerate(c.modifiers))):

            # Delete the nodes
            mod_tree = get_mod_tree(c)
            Modifier.delete_modifier_nodes(mod_tree, mod)
            c.modifiers.remove(j)

        # Remove channel transition effects
        if rch.type == 'NORMAL' and c.enable_transition_bump: 
            c.enable_transition_bump = False
            c.show_transition_bump = False
        else:
            if c.enable_transition_ao:
                c.enable_transition_ao = False
                c.show_transition_ao = False
            if c.enable_transition_ramp:
                c.enable_transition_ramp = False
                c.show_transition_ramp = False

    # Remove layer masks
    for i, m in enumerate(layer.masks):
        Mask.remove_mask(layer, m, bpy.context.object)

class YMergeLayer(bpy.types.Operator, BaseBakeOperator):
    bl_idname = "wm.y_merge_layer"
    bl_label = "Merge layer"
    bl_description = "Merge Layer"
    bl_options = {'REGISTER', 'UNDO'}

    direction : EnumProperty(
        name = 'Direction',
        items = (
            ('UP', 'Up', ''),
            ('DOWN', 'Down', '')
        ),
        default = 'UP'
    )

    channel_idx : EnumProperty(
        name = 'Channel',
        description = 'Channel for merge reference',
        items = merge_channel_items
    )

    apply_modifiers : BoolProperty(
        name = 'Apply Layer Modifiers',
        description = 'Apply layer modifiers',
        default = False
    )

    apply_neighbor_modifiers : BoolProperty(
        name = 'Apply Neighbor Modifiers',
        description = 'Apply neighbor modifiers',
        default = True
    )

    #height_aware : BoolProperty(
    #        name = 'Height Aware',
    #        description = 'Height will take account for merge',
    #        default = True)

    @classmethod
    def poll(cls, context):
        group_node = get_active_ypaint_node()
        return (
            context.object and group_node
                and len(group_node.node_tree.yp.layers) > 0 
                and len(group_node.node_tree.yp.channels) > 0
        )

    def invoke(self, context, event):
        self.invoke_operator(context)

        node = get_active_ypaint_node()
        yp = node.node_tree.yp

        # Get active layer
        layer_idx = self.layer_idx = yp.active_layer_index
        layer = self.layer = yp.layers[layer_idx]

        self.error_message = ''

        enabled_chs =  [ch for ch in layer.channels if ch.enable]
        if not any(enabled_chs):
            self.error_message = "Need at least one layer channel enabled!"

        if self.direction == 'UP':
            neighbor_idx, neighbor_layer = self.neighbor_idx, self.neighbor_layer = get_upper_neighbor(layer)
        elif self.direction == 'DOWN':
            neighbor_idx, neighbor_layer = self.neighbor_idx, self.neighbor_layer = get_lower_neighbor(layer)

        if not neighbor_layer:
            self.error_message = "No neighbor found!"

        elif not neighbor_layer.enable or not layer.enable:
            self.error_message = "Both layer should be enabled!"

        elif neighbor_layer.parent_idx != layer.parent_idx:
            self.error_message = "Cannot merge with layer with different parent!"

        elif neighbor_layer.type == 'GROUP' or layer.type == 'GROUP':
            self.error_message = "Merge doesn't works with layer group!"

        # Get height channnel
        height_root_ch = self.height_root_ch = get_root_height_channel(yp)

        if height_root_ch and neighbor_layer:
            height_ch_idx = self.height_ch_idx = get_channel_index(height_root_ch)
            height_ch = self.height_ch = layer.channels[height_ch_idx] 
            neighbor_height_ch = self.neighbor_height_ch = neighbor_layer.channels[height_ch_idx] 

            if (layer.channels[height_ch_idx].enable and 
                neighbor_layer.channels[height_ch_idx].enable):
                if height_ch.normal_map_type != neighbor_height_ch.normal_map_type:
                    self.error_message =  "These two layers has different normal map type!"
        else:
            height_ch = self.height_ch = None
            neighbor_height_ch = self.neighbor_height_ch = None

        # Get source
        self.source = get_layer_source(layer)

        if layer.type == 'IMAGE':
            if not self.source.image:
                self.error_message = "This layer has no image!"

        if self.error_message != '':
            return self.execute(context)

        # Set default value for channel index
        for i, c in enumerate(layer.channels):
            nc = neighbor_layer.channels[i]
            if c.enable and nc.enable:
                self.channel_idx = str(i)
                break

        # Check if there's any unsaved images
        self.any_dirty_images = any_dirty_images_inside_layer(neighbor_layer) or any_dirty_images_inside_layer(layer)

        # Blender 2.7x has no global undo between modes
        self.legacy_on_non_object_mode = not is_bl_newer_than(2, 80) and context.object.mode != 'OBJECT'

        return context.window_manager.invoke_props_dialog(self, width=320)

    def draw(self, context):
        row = split_layout(self.layout, 0.5)

        col = row.column(align=False)
        col.label(text='Main Channel:')
        col.label(text='Apply Modifiers:')
        col.label(text='Apply Neighbor Modifiers:')

        col = row.column(align=False)
        col.prop(self, 'channel_idx', text='')
        col.prop(self, 'apply_modifiers', text='')
        col.prop(self, 'apply_neighbor_modifiers', text='')

        if self.legacy_on_non_object_mode:
            col = self.layout.column(align=True)
            col.label(text='You cannot UNDO this operation in this mode.', icon='ERROR')
            col.label(text="Are you sure you want to continue?", icon='BLANK1')
        elif self.any_dirty_images:
            col = self.layout.column(align=True)
            col.label(text="Unsaved data will be LOST if you UNDO this operation.", icon='ERROR')
            col.label(text="Are you sure you want to continue?", icon='BLANK1')

    def execute(self, context):
        if not self.is_cycles_exist(context): return {'CANCELLED'}

        if hasattr(self, 'error_message') and self.error_message != '':
            self.report({'ERROR'}, self.error_message)
            return {'CANCELLED'}

        T = time.time()

        wm = context.window_manager
        node = get_active_ypaint_node()
        tree = node.node_tree
        yp = tree.yp
        obj = context.object
        mat = obj.active_material
        scene = context.scene
        objs = get_all_objects_with_same_materials(mat, True)

        # Localize variables
        layer = self.layer
        layer_idx = self.layer_idx
        neighbor_layer = self.neighbor_layer
        neighbor_idx = self.neighbor_idx
        source = self.source

        # Height channel
        height_root_ch = self.height_root_ch
        height_ch = self.height_ch
        neighbor_height_ch = self.neighbor_height_ch

        # Get main reference channel
        main_ch = yp.channels[int(self.channel_idx)]
        ch = layer.channels[int(self.channel_idx)]
        neighbor_ch = neighbor_layer.channels[int(self.channel_idx)]
        
        # Get parent dict
        parent_dict = get_parent_dict(yp)  

        merge_success = False

        # Merge image layers
        if (layer.type == 'IMAGE' and layer.texcoord_type == 'UV'): # and neighbor_layer.type == 'IMAGE'):


            book = remember_before_bake(yp)
            prepare_bake_settings(
                book, objs, yp, samples=1, margin=5, 
                uv_map=layer.uv_name, bake_type='EMIT',
                bake_device = self.bake_device
            )

            # Merge objects if necessary
            temp_objs = []
            if len(objs) > 1 and not is_join_objects_problematic(yp):
                objs = temp_objs = [get_merged_mesh_objects(scene, objs)]

            # Get list of parent ids
            pids = get_list_of_parent_ids(layer)

            # Disable other layers
            layer_oris = []
            for i, l in enumerate(yp.layers):
                layer_oris.append(l.enable)
                if i in pids or l in {layer, neighbor_layer}:
                    l.enable = True
                else: l.enable = False

            # Disable modfiers and transformations if apply modifiers is not enabled
            if not self.apply_modifiers:
                mod_oris = remember_and_disable_layer_modifiers_and_transforms(layer, True)

            if not self.apply_neighbor_modifiers:
                neighbor_oris = remember_and_disable_layer_modifiers_and_transforms(neighbor_layer, False)

            # Make sure to Use mix on layer channel
            if main_ch.type != 'NORMAL':
                ori_blend_type = ch.blend_type
                ch.blend_type = 'MIX'
            else:
                ori_blend_type = ch.normal_blend_type
                ch.normal_blend_type = 'MIX'

            # Enable alpha on main channel (will also update all the nodes)
            ori_enable_alpha = main_ch.enable_alpha
            yp.alpha_auto_setup = False
            main_ch.enable_alpha = True

            # Reconnect tree with merged layer ids
            reconnect_yp_nodes(tree, [layer_idx, neighbor_idx])

            # Bake main channel
            merge_success = bake_channel(layer.uv_name, mat, node, main_ch, target_layer=layer)

            # Remove temporary objects
            if temp_objs:
                for o in temp_objs:
                    remove_mesh_obj(o)

            # Recover bake settings
            recover_bake_settings(book, yp)

            if not self.apply_modifiers:
                recover_layer_modifiers_and_transforms(layer, mod_oris)
            else: remove_layer_modifiers_and_transforms(layer)

            # Recover layer enable
            for i, le in enumerate(layer_oris):
                if yp.layers[i].enable != le:
                    yp.layers[i].enable = le

            # Recover original props
            main_ch.enable_alpha = ori_enable_alpha
            yp.alpha_auto_setup = True
            if main_ch.type != 'NORMAL':
                ch.blend_type = ori_blend_type
            else: ch.normal_blend_type = ori_blend_type

            # Set all channel intensity value to 1.0
            for c in layer.channels:
                c.intensity_value = 1.0

        # Merge vertex color layers
        elif layer.type == 'VCOL' and neighbor_layer.type == 'VCOL':

            modifier_found = False
            if any(layer.modifiers) or any(neighbor_layer.modifiers):
                modifier_found = True

            for c in layer.channels:
                if c.enable and any(c.modifiers):
                    modifier_found = True

            for c in neighbor_layer.channels:
                if c.enable and any(c.modifiers):
                    modifier_found = True

            if any(layer.masks) or any(neighbor_layer.masks):
                modifier_found = True

            if modifier_found:
                self.report({'ERROR'}, "Vertex color merge does not works with modifers and masks yet!")
                return {'CANCELLED'}

            if ch.blend_type != 'MIX' or neighbor_ch.blend_type != 'MIX':
                self.report({'ERROR'}, "Vertex color merge only works with Mix blend type for now!")
                return {'CANCELLED'}

            if neighbor_idx > layer_idx:
                upper_layer = layer
                upper_ch = ch
                lower_layer = neighbor_layer
                lower_ch = neighbor_ch
            else:
                upper_layer = neighbor_layer
                upper_ch = neighbor_ch
                lower_layer = layer
                lower_ch = ch

            ori_obj = context.object

            for obj in objs:

                set_active_object(obj)
                ori_mode = obj.mode

                if ori_mode != 'OBJECT':
                    bpy.ops.object.mode_set(mode='OBJECT')

                upper_vcol = get_layer_vcol(obj, upper_layer)
                lower_vcol = get_layer_vcol(obj, lower_layer)

                if upper_vcol and lower_vcol:

                    cols = numpy.zeros(len(obj.data.loops) * 4, dtype=numpy.float32)
                    cols.shape = (cols.shape[0] // 4, 4)

                    for i, l in enumerate(obj.data.loops):
                        cols[i] = blend_color_mix_byte(lower_vcol.data[i].color, upper_vcol.data[i].color, 
                                lower_ch.intensity_value, upper_ch.intensity_value)
                    
                    vcol = get_layer_vcol(obj, layer)
                    vcol.data.foreach_set('color', cols.ravel())

                    bpy.ops.object.mode_set(mode='VERTEX_PAINT')
                    bpy.ops.object.mode_set(mode='OBJECT')
                    if ori_mode != 'OBJECT':
                        bpy.ops.object.mode_set(mode=ori_mode)

            set_active_object(ori_obj)

            # Set all channel intensity value to 1.0
            for c in layer.channels:
                c.intensity_value = 1.0

            merge_success = True

        else:
            self.report({'ERROR'}, "This kind of merge is not supported yet!")
            return {'CANCELLED'}

        if merge_success:
            # Remove neighbor layer
            Layer.remove_layer(yp, neighbor_idx)

            # Remap parents
            for lay in yp.layers:
                lay.parent_idx = get_layer_index_by_name(yp, parent_dict[lay.name])

            if height_ch and main_ch.type == 'NORMAL' and height_ch.normal_map_type == 'BUMP_MAP':
                height_ch.bump_distance = max_height

            reconnect_yp_nodes(tree)
            rearrange_yp_nodes(tree)

            # Refresh index routine
            yp.active_layer_index = min(layer_idx, neighbor_idx)

            # Update list items
            ListItem.refresh_list_items(yp, repoint_active=True)
        else:
            self.report({'ERROR'}, "Merge failed for some reason!")
            return {'CANCELLED'}

        return {'FINISHED'}

class YMergeMask(bpy.types.Operator, BaseBakeOperator):
    bl_idname = "wm.y_merge_mask"
    bl_label = "Merge mask"
    bl_description = "Merge Mask"
    bl_options = {'UNDO'}

    direction : EnumProperty(
        name = 'Direction',
        items = (
            ('UP', 'Up', ''),
            ('DOWN', 'Down', '')
        ),
        default = 'UP'
    )

    @classmethod
    def poll(cls, context):
        return get_active_ypaint_node()

    def invoke(self, context, event):
        self.invoke_operator(context)

        layer = self.layer = context.layer
        mask = self.mask = context.mask

        # Get neighbor mask
        m = re.match(r'yp\.layers\[(\d+)\]\.masks\[(\d+)\]', mask.path_from_id())
        index = int(m.group(2))
        if self.direction == 'UP':
            try: neighbor_mask = layer.masks[index - 1]
            except: neighbor_mask = None
        else:
            try: neighbor_mask = layer.masks[index + 1]
            except: neighbor_mask = None

        # Blender 2.7x has no global undo between modes
        self.legacy_on_non_object_mode = not is_bl_newer_than(2, 80) and context.object.mode != 'OBJECT'

        # Check for any dirty images
        self.any_dirty_images = False
        if neighbor_mask:
            source = get_mask_source(mask)
            image = source.image if mask.type == 'IMAGE' else None
            neighbor_image = get_mask_source(neighbor_mask).image if neighbor_mask.type == 'IMAGE' else None

            if (image and image.is_dirty) or (neighbor_image and neighbor_image.is_dirty):
                self.any_dirty_images = True

        if self.any_dirty_images or self.legacy_on_non_object_mode:
            return context.window_manager.invoke_props_dialog(self, width=300)

        return self.execute(context)

    def draw(self, context):
        col = self.layout.column(align=True)
        if self.legacy_on_non_object_mode:
            col.label(text='You cannot UNDO this operation in this mode.', icon='ERROR')
            col.label(text="Are you sure you want to continue?", icon='BLANK1')
        else:
            col.label(text="Unsaved data will be LOST if you UNDO this operation.", icon='ERROR')
            col.label(text="Are you sure you want to continue?", icon='BLANK1')

    def check(self, context):
        return True

    def execute(self, context):
        if not self.is_cycles_exist(context): return {'CANCELLED'}

        mask = self.mask
        layer = self.layer
        yp = layer.id_data.yp
        obj = context.object
        mat = obj.active_material
        scene = context.scene
        node = get_active_ypaint_node()

        # Get number of masks
        num_masks = len(layer.masks)
        if num_masks < 2: return {'CANCELLED'}

        # Get mask index
        m = re.match(r'yp\.layers\[(\d+)\]\.masks\[(\d+)\]', mask.path_from_id())
        index = int(m.group(2))

        # Get neighbor index
        if self.direction == 'UP' and index > 0:
            neighbor_idx = index - 1
        elif self.direction == 'DOWN' and index < num_masks-1:
            neighbor_idx = index + 1
        else:
            self.report({'ERROR'}, "No valid neighbor mask!")
            return {'CANCELLED'}

        if mask.type != 'IMAGE':
            self.report({'ERROR'}, "Need image mask!")
            return {'CANCELLED'}

        # Get source
        source = get_mask_source(mask)
        if not source.image:
            self.report({'ERROR'}, "Mask image is missing!")
            return {'CANCELLED'}

        # Target image
        segment = None
        if source.image.yia.is_image_atlas and mask.segment_name != '':
            segment = source.image.yia.segments.get(mask.segment_name)
            width = segment.width
            height = segment.height

            img = bpy.data.images.new(
                name='__TEMP', width=width, height=height,
                alpha=True, float_buffer=source.image.is_float
            )

            if source.image.yia.color == 'WHITE':
                img.generated_color = (1.0, 1.0, 1.0, 1.0)
            elif source.image.yia.color == 'BLACK':
                img.generated_color = (0.0, 0.0, 0.0, 1.0)
            else: img.generated_color = (0.0, 0.0, 0.0, 0.0)

            img.colorspace_settings.name = get_noncolor_name()
        else:
            img = source.image.copy()
            width = img.size[0]
            height = img.size[1]

        # Activate layer preview mode
        ori_layer_preview_mode = yp.layer_preview_mode
        yp.layer_preview_mode = True

        # Get neighbor mask
        neighbor_mask = layer.masks[neighbor_idx]

        # Get layer tree
        tree = get_tree(layer)

        # Create mask mix nodes
        for m in [mask, neighbor_mask]:
            mix = new_mix_node(tree, m, 'mix', 'Mix')
            mix.blend_type = m.blend_type
            mix.inputs[0].default_value = m.intensity_value

            # Replace linear to more accurate ones
            linear = tree.nodes.get(m.linear)
            if linear:
                linear = replace_new_node(tree, m, 'linear', 'ShaderNodeGroup', 'Linear')
                linear.node_tree = get_node_tree_lib(lib.LINEAR_2_SRGB)

        # Reconnect nodes
        reconnect_layer_nodes(layer, merge_mask=True)
        rearrange_layer_nodes(layer)

        # Prepare to bake
        objs = get_all_objects_with_same_materials(mat, True)

        book = remember_before_bake(yp)
        prepare_bake_settings(
            book, objs, yp, samples=1, margin=5, 
            uv_map=mask.uv_name, bake_type='EMIT',
            bake_device = self.bake_device
        )

        # Combine objects if possible
        temp_objs = []
        if len(objs) > 1 and not is_join_objects_problematic(yp):
            objs = temp_objs = [get_merged_mesh_objects(scene, objs)]

        # Get material output
        output = get_active_mat_output_node(mat.node_tree)
        ori_bsdf = output.inputs[0].links[0].from_socket

        # Create bake nodes
        tex = mat.node_tree.nodes.new('ShaderNodeTexImage')
        emit = mat.node_tree.nodes.new('ShaderNodeEmission')

        # Set image
        tex.image = img
        mat.node_tree.nodes.active = tex

        # Connect
        mat.node_tree.links.new(node.outputs[LAYER_ALPHA_VIEWER], emit.inputs[0])
        mat.node_tree.links.new(emit.outputs[0], output.inputs[0])

        #return {'FINISHED'}

        # Bake
        bake_object_op()

        # Copy results to original image
        copy_image_pixels(img, source.image, segment)

        # HACK: Pack and refresh to update image in Blender 2.77 and lower
        if not is_bl_newer_than(2, 78) and (source.image.packed_file or source.image.filepath == ''):
            if source.image.is_float:
                image_ops.pack_float_image(source.image)
            else: source.image.pack(as_png=True)
            source.image.reload()

        # Remove temp image
        remove_datablock(bpy.data.images, img, user=tex, user_prop='image')

        # Remove mask mix nodes
        for m in [mask, neighbor_mask]:
            remove_node(tree, m, 'mix')

            # Replace linear to less accurate ones
            linear = tree.nodes.get(m.linear)
            if linear:
                linear = replace_new_node(tree, m, 'linear', 'ShaderNodeGamma', 'Linear')
                linear.inputs[1].default_value = 1.0 / GAMMA

        # Remove modifiers
        for i, mod in reversed(list(enumerate(mask.modifiers))):
            MaskModifier.delete_modifier_nodes(tree, mod)
            mask.modifiers.remove(i)

        # Remove neighbor mask
        Mask.remove_mask(layer, neighbor_mask, obj)

        # Remove bake nodes
        simple_remove_node(mat.node_tree, tex)
        simple_remove_node(mat.node_tree, emit)

        # Recover original bsdf
        mat.node_tree.links.new(ori_bsdf, output.inputs[0])

        # Remove temporary objects
        if temp_objs:
            for o in temp_objs:
                remove_mesh_obj(o)

        # Recover bake settings
        recover_bake_settings(book, yp)

        # Revert back preview mode 
        yp.layer_preview_mode = ori_layer_preview_mode

        # Point to neighbor mask for merge up
        if index > neighbor_idx:
            mask = layer.masks[neighbor_idx]

        # Set current mask as active
        mask.active_edit = True
        yp.active_layer_index = yp.active_layer_index

        return {'FINISHED'}

class YBakeTempImage(bpy.types.Operator, BaseBakeOperator):
    bl_idname = "wm.y_bake_temp_image"
    bl_label = "Bake temporary image of layer"
    bl_description = "Bake temporary image of layer, can be useful to prefent glitching with cycles"
    bl_options = {'REGISTER', 'UNDO'}

    uv_map : StringProperty(default='')
    uv_map_coll : CollectionProperty(type=bpy.types.PropertyGroup)

    hdr : BoolProperty(name='32 bit Float', default=True)

    @classmethod
    def poll(cls, context):
        return get_active_ypaint_node() #and hasattr(context, 'parent')

    def invoke(self, context, event):
        self.invoke_operator(context)

        obj = context.object
        ypup = get_user_preferences()

        self.auto_cancel = False
        if not hasattr(context, 'parent'):
            self.auto_cancel = True
            return self.execute(context)

        self.parent = context.parent

        if self.parent.type not in {'HEMI'}:
            self.auto_cancel = True
            return self.execute(context)

        # Use active uv layer name by default
        uv_layers = get_uv_layers(obj)

        # UV Map collections update
        self.uv_map_coll.clear()
        for uv in uv_layers:
            if not uv.name.startswith(TEMP_UV):
                self.uv_map_coll.add().name = uv.name

        if len(self.uv_map_coll) > 0:
            self.uv_map = self.uv_map_coll[0].name

        if get_user_preferences().skip_property_popups and not event.shift:
            return self.execute(context)

        return context.window_manager.invoke_props_dialog(self, width=320)

    def draw(self, context):
        node = get_active_ypaint_node()
        yp = node.node_tree.yp

        row = split_layout(self.layout, 0.4)

        col = row.column(align=False)

        #col.label(text='')
        col.label(text='Width:')
        col.label(text='Height:')
        col.label(text='')
        col.label(text='UV Map:')
        col.label(text='Samples:')

        col.label(text='Margin:')

        col = row.column(align=False)

        #col.prop(self, 'hdr')
        col.prop(self, 'width', text='')
        col.prop(self, 'height', text='')
        col.prop(self, 'hdr')
        col.prop_search(self, "uv_map", self, "uv_map_coll", text='', icon='GROUP_UVS')
        col.prop(self, 'samples', text='')

        if is_bl_newer_than(3, 1):
            split = split_layout(col, 0.4, align=True)
            split.prop(self, 'margin', text='')
            split.prop(self, 'margin_type', text='')
        else:
            col.prop(self, 'margin', text='')

    def execute(self, context):
        if not self.is_cycles_exist(context): return {'CANCELLED'}

        if not hasattr(self, 'parent'):
            self.report({'ERROR'}, "Context is incorrect!")
            return {'CANCELLED'}

        entity = self.parent
        if entity.type not in {'HEMI'}:
            self.report({'ERROR'}, "This layer type is not supported (yet)!")
            return {'CANCELLED'}

        # Bake temp image
        image = temp_bake(
            context, entity, self.width, self.height, self.hdr, self.samples,
            self.margin, self.uv_map, margin_type=self.margin_type,
            bake_device=self.bake_device
        )

        return {'FINISHED'}

class YDisableTempImage(bpy.types.Operator):
    bl_idname = "wm.y_disable_temp_image"
    bl_label = "Disable Baked temporary image of layer"
    bl_description = "Disable bake temporary image of layer"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return get_active_ypaint_node() and hasattr(context, 'parent')

    def execute(self, context):
        entity = context.parent
        if not entity.use_temp_bake:
            self.report({'ERROR'}, "This layer is not temporarily baked!")
            return {'CANCELLED'}

        disable_temp_bake(entity)

        return {'FINISHED'}

def copy_default_value(inp_source, inp_target):
    if inp_target.bl_idname == inp_source.bl_idname:
        inp_target.default_value = inp_source.default_value
    elif isinstance(inp_target.default_value, float) and isinstance(inp_source.default_value, float):
        inp_target.default_value = inp_source.default_value
    elif isinstance(inp_target.default_value, float):
        avg = sum([inp_source.default_value[i] for i in range(3)]) / 3
        inp_target.default_value = avg
    elif isinstance(inp_source.default_value, float):
        for i in range(3):
            inp_target.default_value[i] = inp_source.default_value

def update_enable_baked_outside(self, context):
    tree = self.id_data
    yp = tree.yp
    node = get_active_ypaint_node()
    if not node: return
    mat = get_active_material()
    scene = context.scene
    ypup = get_user_preferences()
    output_mat = get_material_output(mat)

    mtree = mat.node_tree

    if yp.halt_update: return
    #if not yp.use_baked: return

    if yp.enable_baked_outside and yp.use_baked:

        # Shift nodes to the right
        shift_nodes = []
        for n in mtree.nodes:
            if n.location.x > node.location.x:
                shift_nodes.append(n)

        # Baked outside nodes should be contained inside of frame
        frame = mtree.nodes.get(yp.baked_outside_frame)
        if not frame:
            frame = mtree.nodes.new('NodeFrame')
            frame.label = tree.name + ' Baked Textures'
            frame.name = tree.name + ' Baked Textures'
            yp.baked_outside_frame = frame.name

        # Custom bake target images also have their own frame
        bt_frame = mtree.nodes.get(yp.bake_target_outside_frame)
        if not bt_frame:
            bt_frame = mtree.nodes.new('NodeFrame')
            bt_frame.label = tree.name + ' Custom Bake Targets'
            bt_frame.name = tree.name + ' Custom Bake Targets'
            yp.bake_target_outside_frame = bt_frame.name

        loc_x = node.location.x + 180
        loc_y = node.location.y

        uv = check_new_node(mtree, yp, 'baked_outside_uv', 'ShaderNodeUVMap')
        uv.uv_map = yp.baked_uv_name
        uv.location.x = loc_x
        uv.location.y = loc_y
        uv.parent = frame

        color_ch, alpha_ch = get_color_alpha_ch_pairs(yp)

        loc_x += 180
        max_x = loc_x

        for ch in yp.channels:

            # Remember current connection
            outp = node.outputs.get(ch.name)
            for l in outp.links:
                con = ch.ori_to.add()
                con.node = l.to_node.name
                con.socket = l.to_socket.name
                con.socket_index = get_node_input_index(l.to_node, l.to_socket)

            outp_alpha = None
            if ch.enable_alpha:
                outp_alpha = node.outputs.get(ch.name + io_suffix['ALPHA'])
            elif ch == color_ch:
                baked_alpha = tree.nodes.get(alpha_ch.baked)
                if not baked_alpha:
                    outp_alpha = node.outputs.get(alpha_ch.name)

            if outp_alpha:
                for l in outp_alpha.links:
                    con = ch.ori_alpha_to.add()
                    con.node = l.to_node.name
                    con.socket = l.to_socket.name
                    con.socket_index = get_node_input_index(l.to_node, l.to_socket)

            outp_height = node.outputs.get(ch.name + io_suffix['HEIGHT'])
            if outp_height:
                for l in outp_height.links:
                    con = ch.ori_height_to.add()
                    con.node = l.to_node.name
                    con.socket = l.to_socket.name
                    con.socket_index = get_node_input_index(l.to_node, l.to_socket)

            outp_mheight = node.outputs.get(ch.name + io_suffix['MAX_HEIGHT'])
            if outp_mheight:
                for l in outp_mheight.links:
                    con = ch.ori_max_height_to.add()
                    con.node = l.to_node.name
                    con.socket = l.to_socket.name
                    con.socket_index = get_node_input_index(l.to_node, l.to_socket)

            baked = tree.nodes.get(ch.baked)
            if baked and baked.image and not ch.no_layer_using:
                tex = check_new_node(mtree, ch, 'baked_outside', 'ShaderNodeTexImage')
                tex.image = baked.image
                tex.location.x = loc_x
                tex.location.y = loc_y
                tex.parent = frame
                tex.interpolation = baked.interpolation
                mtree.links.new(uv.outputs[0], tex.inputs[0])

                baked_vcol = tree.nodes.get(ch.baked_vcol)
                vcol = None
                if baked_vcol and ch.enable_bake_to_vcol:
                    vcol = check_new_node(mtree, ch, 'baked_outside_vcol', get_vcol_bl_idname())
                    set_source_vcol_name(vcol, ch.bake_to_vcol_name)
                    loc_x += 280
                    vcol.location.x = loc_x
                    vcol.location.y = loc_y - 100
                    vcol.parent = frame
                    max_x = loc_x
                    loc_x -= 280

                if not is_bl_newer_than(2, 80) and baked.image.colorspace_settings.name != get_srgb_name():
                    tex.color_space = 'NONE'

                if outp_alpha:
                    for l in outp_alpha.links:
                        if vcol and ch.enable_bake_to_vcol:
                            mtree.links.new(vcol.outputs['Alpha'], l.to_socket)
                        else:
                            mtree.links.new(tex.outputs[1], l.to_socket)

                if ch.type != 'NORMAL':

                    for l in outp.links:
                        if vcol and ch.enable_bake_to_vcol:
                            outp_name = 'Alpha' if ch.bake_to_vcol_alpha else 'Color'
                            mtree.links.new(vcol.outputs[outp_name], l.to_socket)
                        else:
                            mtree.links.new(tex.outputs[0], l.to_socket)
                else:

                    loc_x += 280
                    norm = check_new_node(mtree, ch, 'baked_outside_normal_process', 'ShaderNodeNormalMap')
                    norm.uv_map = yp.baked_uv_name
                    norm.location.x = loc_x
                    norm.location.y = loc_y
                    norm.parent = frame
                    max_x = loc_x
                    if vcol:
                        vcol.location.x += 180
                        max_x = loc_x + 180
                    loc_x -= 280

                    mtree.links.new(tex.outputs[0], norm.inputs[1])

                    baked_normal_overlay = None
                    if not is_overlay_normal_empty(yp):
                        baked_normal_overlay = tree.nodes.get(ch.baked_normal_overlay)
                        if baked_normal_overlay and baked_normal_overlay.image:
                            loc_y -= 300
                            tex_normal_overlay = check_new_node(mtree, ch, 'baked_outside_normal_overlay', 'ShaderNodeTexImage')
                            tex_normal_overlay.image = baked_normal_overlay.image
                            tex_normal_overlay.location.x = loc_x
                            tex_normal_overlay.location.y = loc_y
                            tex_normal_overlay.parent = frame
                            mtree.links.new(uv.outputs[0], tex_normal_overlay.inputs[0])

                            if not is_bl_newer_than(2, 80) and baked_normal_overlay.image.colorspace_settings.name != get_srgb_name():
                                tex_normal_overlay.color_space = 'NONE'

                            if ch.enable_subdiv_setup:
                                mtree.links.new(tex_normal_overlay.outputs[0], norm.inputs[1])

                    #if not ch.enable_subdiv_setup or baked_normal_overlay:
                    for l in outp.links:
                        mtree.links.new(norm.outputs[0], l.to_socket)

                    baked_disp = tree.nodes.get(ch.baked_disp)
                    baked_vdisp = tree.nodes.get(ch.baked_vdisp)
                    disp_add = None

                    # Remember original displacement connection
                    if output_mat:
                        for link in output_mat.inputs['Displacement'].links:
                            ch.baked_outside_ori_disp_from_node = link.from_node.name
                            ch.baked_outside_ori_disp_from_socket = link.from_socket.name
                            break

                    # Displacement addition node
                    if baked_disp and baked_disp.image and baked_vdisp and baked_vdisp.image:
                        disp_add = check_new_node(mtree, ch, 'baked_outside_disp_addition', 'ShaderNodeVectorMath')
                        if ch.enable_subdiv_setup and output_mat:
                            mtree.links.new(disp_add.outputs[0], output_mat.inputs['Displacement'])

                    if baked_disp and baked_disp.image:
                        loc_y -= 300
                        tex_disp = check_new_node(mtree, ch, 'baked_outside_disp', 'ShaderNodeTexImage')
                        tex_disp.image = baked_disp.image
                        tex_disp.location.x = loc_x
                        tex_disp.location.y = loc_y
                        tex_disp.parent = frame
                        tex_disp.interpolation = 'Cubic'
                        mtree.links.new(uv.outputs[0], tex_disp.inputs[0])

                        if not is_bl_newer_than(2, 80) and baked_disp.image.colorspace_settings.name != get_srgb_name():
                            tex_disp.color_space = 'NONE'

                        loc_x += 280
                        disp = create_displacement_node(mat.node_tree)
                        disp.location.x = loc_x
                        disp.location.y = loc_y
                        disp.parent = frame
                        ch.baked_outside_disp_process = disp.name

                        if disp_add:
                            loc_x += 200
                            disp_add.location.x = loc_x
                            disp_add.location.y = loc_y
                            disp_add.parent = frame
                            max_x = loc_x
                            loc_x -= 480
                        else:
                            max_x = loc_x
                            loc_x -= 280

                        mtree.links.new(tex_disp.outputs[0], disp.inputs[0])

                        # Set max height
                        end_max_height = node.node_tree.nodes.get(ch.end_max_height)
                        if end_max_height:
                            disp.inputs['Scale'].default_value = end_max_height.outputs[0].default_value

                        # Target socket
                        target_socket = None
                        if disp_add:
                            target_socket = disp_add.inputs[0]
                        elif ch.enable_subdiv_setup and output_mat:
                            target_socket = output_mat.inputs['Displacement']

                        # Connect to target socket
                        if target_socket:
                            mtree.links.new(disp.outputs[0], target_socket)

                    if baked_vdisp and baked_vdisp.image:
                        loc_y -= 300
                        tex_vdisp = check_new_node(mtree, ch, 'baked_outside_vdisp', 'ShaderNodeTexImage')
                        tex_vdisp.image = baked_vdisp.image
                        tex_vdisp.location.x = loc_x
                        tex_vdisp.location.y = loc_y
                        tex_vdisp.parent = frame
                        tex_vdisp.interpolation = 'Cubic'
                        mtree.links.new(uv.outputs[0], tex_vdisp.inputs[0])

                        if not is_bl_newer_than(2, 80) and baked_vdisp.image.colorspace_settings.name != get_srgb_name():
                            tex_vdisp.color_space = 'NONE'

                        loc_x += 280
                        vdisp = create_vector_displacement_node(mat.node_tree)
                        vdisp.location.x = loc_x
                        vdisp.location.y = loc_y
                        vdisp.parent = frame
                        ch.baked_outside_vdisp_process = vdisp.name
                        max_x = loc_x
                        loc_x -= 280

                        mtree.links.new(tex_vdisp.outputs[0], vdisp.inputs[0])

                        # Target socket
                        target_socket = None
                        if disp_add:
                            target_socket = disp_add.inputs[1]
                        elif ch.enable_subdiv_setup and output_mat:
                            target_socket = output_mat.inputs['Displacement']

                        # Connect to target socket
                        if target_socket:
                            mtree.links.new(vdisp.outputs[0], target_socket)

                    if ch.enable_bake_to_vcol:
                        mtree.links.new(vcol.outputs['Color'], l.to_socket)
                loc_y -= 300

                # Create GLTF material output node so AO can be included in Blender's automated ORM texture
                if ch.name in {'Ambient Occlusion', 'Occlusion', 'AO', 'Specular', 'Specular Color', 'Thickness'}:
                    node_name = lib.GLTF_MATERIAL_OUTPUT if is_bl_newer_than(3, 4) else lib.GLTF_SETTINGS
                    gltf_outp = mtree.nodes.get(node_name)
                    if not gltf_outp:
                        gltf_outp = mtree.nodes.new('ShaderNodeGroup')
                        gltf_outp.node_tree = get_node_tree_lib(node_name)
                        gltf_outp.name = node_name
                        gltf_outp.label = node_name
                        gltf_outp.location.x = output_mat.location.x
                        gltf_outp.location.y = output_mat.location.y + 200
                        shift_nodes.append(gltf_outp)

                    if ch.name in {'Ambient Occlusion', 'Occlusion', 'AO'} and 'Occlusion' in gltf_outp.inputs:
                        mtree.links.new(tex.outputs[0], gltf_outp.inputs['Occlusion'])
                    elif ch.name == 'Thickness' and 'Thickness' in gltf_outp.inputs:
                        mtree.links.new(tex.outputs[0], gltf_outp.inputs['Thickness'])
                    elif ch.name == 'Specular':
                        if 'Specular' in gltf_outp.inputs:
                            mtree.links.new(tex.outputs[0], gltf_outp.inputs['Specular'])
                        elif 'specular glTF' in gltf_outp.inputs:
                            mtree.links.new(tex.outputs[0], gltf_outp.inputs['specular glTF'])
                    elif ch.name == 'Specular Color':
                        if 'Specular Color' in gltf_outp.inputs:
                            mtree.links.new(tex.outputs[0], gltf_outp.inputs['Specular Color'])
                        elif 'specularColor glTF' in gltf_outp.inputs:
                            mtree.links.new(tex.outputs[0], gltf_outp.inputs['specularColor glTF'])

            else:

                # Copy yp default value to connected nodes
                inp = node.inputs.get(ch.name)
                for l in outp.links:
                    copy_default_value(inp, l.to_socket)

                inp_alpha = node.inputs.get(ch.name + io_suffix['ALPHA'])
                if inp_alpha and outp_alpha:
                    for l in outp_alpha.links:
                        copy_default_value(inp_alpha, l.to_socket)

                inp_height = node.inputs.get(ch.name + io_suffix['HEIGHT'])
                if inp_height and outp_height:
                    for l in outp_height.links:
                        copy_default_value(inp_height, l.to_socket)

        # Bake targets
        first_bt_found = False
        for bt in yp.bake_targets:
            image_node = tree.nodes.get(bt.image_node)
            if image_node and image_node.image:

                if not first_bt_found:
                    loc_y -= 75
                    first_bt_found = True

                tex = check_new_node(mtree, bt, 'image_node_outside', 'ShaderNodeTexImage')
                tex.image = image_node.image
                tex.location.x = loc_x
                tex.location.y = loc_y
                tex.parent = bt_frame
                mtree.links.new(uv.outputs[0], tex.inputs[0])

                loc_y -= 300

        if not first_bt_found:
            remove_node(mtree, yp, 'bake_target_outside_frame')

        # Remove links
        for outp in node.outputs:
            for l in outp.links:
                mtree.links.remove(l)

        loc_x = max_x + 100
        yp.baked_outside_x_shift = int(loc_x - node.location.x)

        for n in shift_nodes:
            n.location.x += yp.baked_outside_x_shift

    else:
        baked_outside_frame = mtree.nodes.get(yp.baked_outside_frame)
        bake_target_outside_frame = mtree.nodes.get(yp.bake_target_outside_frame)

        color_ch, alpha_ch = get_color_alpha_ch_pairs(yp)

        # Channels
        for ch in yp.channels:

            outp = node.outputs.get(ch.name)
            connect_to_original_node(mtree, outp, ch.ori_to)
            ch.ori_to.clear()

            outp_alpha = None
            if ch.enable_alpha:
                outp_alpha = node.outputs.get(ch.name + io_suffix['ALPHA'])
            elif ch == color_ch:
                baked_alpha = tree.nodes.get(alpha_ch.baked)
                if not baked_alpha:
                    outp_alpha = node.outputs.get(alpha_ch.name)

            if outp_alpha:
                connect_to_original_node(mtree, outp_alpha, ch.ori_alpha_to)
                ch.ori_alpha_to.clear()

            outp_height = node.outputs.get(ch.name + io_suffix['HEIGHT'])
            if outp_height:
                connect_to_original_node(mtree, outp_height, ch.ori_height_to)
                ch.ori_height_to.clear()

            outp_mheight = node.outputs.get(ch.name + io_suffix['MAX_HEIGHT'])
            if outp_mheight:
                connect_to_original_node(mtree, outp_mheight, ch.ori_max_height_to)
                ch.ori_max_height_to.clear()

            # Delete nodes inside frames
            if baked_outside_frame:
                remove_node(mtree, ch, 'baked_outside', parent=baked_outside_frame)
                remove_node(mtree, ch, 'baked_outside_vcol', parent=baked_outside_frame)
                remove_node(mtree, ch, 'baked_outside_disp', parent=baked_outside_frame)
                remove_node(mtree, ch, 'baked_outside_vdisp', parent=baked_outside_frame)
                remove_node(mtree, ch, 'baked_outside_normal_overlay', parent=baked_outside_frame)
                remove_node(mtree, ch, 'baked_outside_normal_process', parent=baked_outside_frame)
                remove_node(mtree, ch, 'baked_outside_disp_process', parent=baked_outside_frame)
                remove_node(mtree, ch, 'baked_outside_vdisp_process', parent=baked_outside_frame)
                remove_node(mtree, ch, 'baked_outside_disp_addition', parent=baked_outside_frame)

        # Bake targets
        for bt in yp.bake_targets:
            remove_node(mtree, bt, 'image_node_outside', parent=bake_target_outside_frame)

        if baked_outside_frame:
            remove_node(mtree, yp, 'baked_outside_uv', parent=baked_outside_frame)
            remove_node(mtree, yp, 'baked_outside_frame')

        if bake_target_outside_frame:
            remove_node(mtree, yp, 'bake_target_outside_frame')

        # Shift back nodes location
        for n in mtree.nodes:
            if n.location.x > node.location.x:
                n.location.x -= yp.baked_outside_x_shift
        yp.baked_outside_x_shift = 0

        # Set back adaptive displacement node
        height_ch = get_root_height_channel(yp)
        if height_ch:

            # Recover displacement connection
            if height_ch.baked_outside_ori_disp_from_node != '':
                nod = mat.node_tree.nodes.get(height_ch.baked_outside_ori_disp_from_node)
                if nod: 
                    soc = nod.outputs.get(height_ch.baked_outside_ori_disp_from_socket)
                    if soc and output_mat:
                        mat.node_tree.links.new(soc, output_mat.inputs['Displacement'])
                height_ch.baked_outside_ori_disp_from_node = ''
                height_ch.baked_outside_ori_disp_from_socket = ''

            if height_ch.enable_subdiv_setup:

                if height_ch.subdiv_adaptive:
                    # Adaptive subdivision only works for experimental feature set for now
                    scene.cycles.feature_set = 'EXPERIMENTAL'
                    scene.cycles.dicing_rate = height_ch.subdiv_global_dicing
                    scene.cycles.preview_dicing_rate = height_ch.subdiv_global_dicing

                check_displacement_node(mat, node, set_one=True)

def connect_to_original_node(mtree, outp, ori_to):
    for con in ori_to:
        node = mtree.nodes.get(con.node)
        if not node: continue
        # Some mix inputs has same name so use index instead
        if node.type == 'MIX':
            try: mtree.links.new(outp, node.inputs[con.socket_index])
            except Exception as e: print(e)
        else:
            try: mtree.links.new(outp, node.inputs[con.socket])
            except Exception as e: print(e)

def update_use_baked(self, context):
    tree = self.id_data
    yp = tree.yp
    ypup = get_user_preferences()

    if yp.halt_update: return

    # Check subdiv setup
    #height_ch = get_root_height_channel(yp)
    #if height_ch:
    #    if height_ch.enable_subdiv_setup and yp.use_baked and not ypup.eevee_next_displacement:
    #        remember_subsurf_levels()
    #    check_subdiv_setup(height_ch)
    #    if height_ch.enable_subdiv_setup and not yp.use_baked and not ypup.eevee_next_displacement:
    #        recover_subsurf_levels()

    # Check uv nodes
    check_uv_nodes(yp)

    # Check start and end nodes
    check_start_end_root_ch_nodes(tree)

    # Reconnect nodes
    reconnect_yp_nodes(tree)
    rearrange_yp_nodes(tree)

    # Trigger active image update
    if yp.use_baked:
        yp.active_channel_index = yp.active_channel_index
    else:
        yp.active_layer_index = yp.active_layer_index

    # Update baked outside
    update_enable_baked_outside(self, context)

def update_enable_bake_to_vcol(self, context):
    tree = self.id_data
    yp = tree.yp

    if yp.halt_update: return
    if yp.enable_baked_outside:
        # Reset the node location
        yp.enable_baked_outside = False
        yp['enable_baked_outside'] = True
    update_use_baked(self, context)

def is_node_a_displacement(node, is_vector_disp=False):
    if not is_bl_newer_than(2, 80):
        if is_vector_disp: return None
        return node.type == 'GROUP' and node.node_tree and node.node_tree.name == lib.BL27_DISP

    if is_vector_disp: return node.type == 'VECTOR_DISPLACEMENT'
    return node.type == 'DISPLACEMENT'

def get_closest_disp_node_backward(node, socket_name='', is_vector_disp=False):

    # Get input list
    if socket_name != '':
        inp = node.inputs.get(socket_name)
        if not inp: return None
        inputs = [inp]
    else: inputs = node.inputs

    # Search for displacement node
    for inp in inputs:
        for link in inp.links:
            n = link.from_node
            if is_node_a_displacement(n, is_vector_disp=is_vector_disp):
                return n
            else:
                n = get_closest_disp_node_backward(n, is_vector_disp=is_vector_disp)
                if n: return n

    return None

def create_displacement_node(tree, connect_to=None):
    if is_bl_newer_than(2, 80):
        disp = tree.nodes.new('ShaderNodeDisplacement')
    else:
        # Set displacement mode
        disp = tree.nodes.new('ShaderNodeGroup')
        disp.node_tree = get_node_tree_lib(lib.BL27_DISP)

    if connect_to:
        create_link(tree, disp.outputs[0], connect_to)

    return disp

def create_vector_displacement_node(tree, connect_to=None):
    vdisp = None
    if is_bl_newer_than(2, 80):
        vdisp = tree.nodes.new('ShaderNodeVectorDisplacement')

    if vdisp and connect_to:
        create_link(tree, vdisp.outputs[0], connect_to)

    return vdisp

def check_displacement_node(mat, node, set_one=False, unset_one=False, set_outside=False):

    output_mat = get_material_output(mat)
    if not output_mat: return None

    height_ch = get_root_height_channel(node.node_tree.yp)
    if not height_ch: return None

    # Check output connection
    norm_outp = node.outputs[height_ch.name]
    height_outp = node.outputs.get(height_ch.name + io_suffix['HEIGHT'])
    max_height_outp = node.outputs.get(height_ch.name + io_suffix['MAX_HEIGHT'])
    vdisp_outp = node.outputs.get(height_ch.name + io_suffix['VDISP'])
    disp_mat_inp = output_mat.inputs['Displacement']

    disp = get_closest_disp_node_backward(output_mat, 'Displacement')
    vdisp = get_closest_disp_node_backward(output_mat, 'Displacement', is_vector_disp=True)
    add_disp = None

    if set_one or set_outside:
        
        # Set add vector node
        if is_bl_newer_than(2, 80) and ((not disp and not vdisp) or (disp and not vdisp) or (not disp and vdisp)):
            add_disp = mat.node_tree.nodes.new('ShaderNodeVectorMath')

            add_disp.location.x = output_mat.location.x
            add_disp.location.y = node.location.y - 170
            add_disp.hide = True

        # Set displacement
        if not disp:

            # Create displacement node
            disp = create_displacement_node(mat.node_tree) #, disp_mat_inp)

            disp.location.x = output_mat.location.x
            disp.location.y = node.location.y - 220

            # Set displacement node default value
            disp.inputs['Height'].default_value = 0.0
            disp.inputs['Scale'].default_value = 0.0

        elif set_one:
            # Connect the original connections to yp node
            height_inp = None
            for l in disp.inputs['Height'].links:
                if not l.from_socket or l.from_node == node: continue
                height_inp = node.inputs.get(height_ch.name + io_suffix['HEIGHT'])
                if height_inp: create_link(mat.node_tree, l.from_socket, height_inp)

            for l in disp.inputs['Scale'].links:
                if not l.from_socket or l.from_node == node: continue
                max_height_inp = node.inputs.get(height_ch.name + io_suffix['MAX_HEIGHT'])
                if max_height_inp: create_link(mat.node_tree, l.from_socket, max_height_inp)
            
            # Need to check check start and end nodes again if height input is connected
            if height_inp: check_all_channel_ios(node.node_tree.yp, reconnect=False)

        # Set vector displacement
        if not vdisp:

            # Create displacement node
            vdisp = create_vector_displacement_node(mat.node_tree) #, disp_mat_inp)

            if vdisp:
                vdisp.location.x = output_mat.location.x
                vdisp.location.y = node.location.y - 410

                # Set displacement node default value
                vdisp.inputs['Vector'].default_value = (0, 0, 0, 0)

        elif set_one:
            # Connect the original connections to yp node
            vdisp_input = None
            for l in vdisp.inputs['Vector'].links:
                if not l.from_socket or l.from_node == node: continue
                vdisp_input = node.inputs.get(height_ch.name + io_suffix['VDISP'])
                if vdisp_input: create_link(mat.node_tree, l.from_socket, vdisp_input)

        if add_disp and vdisp:
            create_link(mat.node_tree, disp.outputs[0], add_disp.inputs[0])
            create_link(mat.node_tree, vdisp.outputs[0], add_disp.inputs[1])
            create_link(mat.node_tree, add_disp.outputs[0], disp_mat_inp)
        elif disp and not vdisp:
            create_link(mat.node_tree, disp.outputs[0], disp_mat_inp)

        if set_one:
            # Create links
            if vdisp and vdisp_outp: create_link(mat.node_tree, vdisp_outp, vdisp.inputs['Vector'])
            if disp:
                create_link(mat.node_tree, height_outp, disp.inputs['Height'])
                create_link(mat.node_tree, max_height_outp, disp.inputs['Scale'])

    if disp and unset_one:
        height_inp = node.inputs.get(height_ch.name + io_suffix['HEIGHT'])
        max_height_inp = node.inputs.get(height_ch.name + io_suffix['MAX_HEIGHT'])

        if height_inp and len(height_inp.links) > 0:
            soc = height_inp.links[0].from_socket
            create_link(mat.node_tree, soc, disp.inputs['Height'])
            break_input_link(mat.node_tree, height_inp)

        if max_height_inp and len(max_height_inp.links) > 0:
            soc = max_height_inp.links[0].from_socket
            create_link(mat.node_tree, soc, disp.inputs['Scale'])
            break_input_link(mat.node_tree, max_height_inp)

    return disp

def check_subdiv_setup(height_ch):
    tree = height_ch.id_data
    yp = tree.yp
    ypup = get_user_preferences()

    if not height_ch: return
    mat = get_active_material()
    scene = bpy.context.scene
    objs = get_all_objects_with_same_materials(mat, True)

    mtree = mat.node_tree

    # Get active output material
    output_mat = get_material_output(mat)
    if not output_mat: return

    # Get active ypaint node
    node = get_active_ypaint_node()
    norm_outp = node.outputs[height_ch.name]

    # Scene and material displacement settings
    if height_ch.enable_subdiv_setup:

        # Displacement only works with experimental feature set in Blender 2.79
        if height_ch.subdiv_adaptive or not is_bl_newer_than(2, 80):
            scene.cycles.feature_set = 'EXPERIMENTAL'

        if height_ch.subdiv_adaptive:
            scene.cycles.dicing_rate = height_ch.subdiv_global_dicing
            scene.cycles.preview_dicing_rate = height_ch.subdiv_global_dicing

        # Set displacement mode
        if hasattr(mat, 'displacement_method'):
            #mat.displacement_method = 'BOTH'
            mat.displacement_method = 'DISPLACEMENT'

        if is_bl_newer_than(2, 80):
            #mat.cycles.displacement_method = 'BOTH'
            mat.cycles.displacement_method = 'DISPLACEMENT'
        else: mat.cycles.displacement_method = 'TRUE'
        
        # Displacement method is inside object data for Blender 2.77 and below 
        if not is_bl_newer_than(2, 78):
            for obj in objs:
                if obj.data and hasattr(obj.data, 'cycles'):
                    obj.data.cycles.displacement_method = 'TRUE'

        if not yp.use_baked or not yp.enable_baked_outside:
            check_displacement_node(mat, node, set_one=True)

    # Outside nodes connection set
    #if yp.use_baked and yp.enable_baked_outside:
    #    frame = get_node(mtree, yp.baked_outside_frame)
    #    norm = get_node(mtree, height_ch.baked_outside_normal_process, parent=frame)
    #    disp = get_node(mtree, height_ch.baked_outside_disp_process, parent=frame)
    #    baked_outside = get_node(mtree, height_ch.baked_outside, parent=frame)
    #    baked_outside_normal_overlay = get_node(mtree, height_ch.baked_outside_normal_overlay, parent=frame)

    #    if height_ch.enable_subdiv_setup:
    #        if disp:
    #            create_link(mtree, disp.outputs[0], output_mat.inputs['Displacement'])
    #        if baked_outside and norm:
    #            create_link(mtree, baked_outside.outputs[0], norm.inputs[1])
    #    else:
    #        if baked_outside and norm:
    #            create_link(mtree, baked_outside.outputs[0], norm.inputs[1])
    #    
    #    if norm and not baked_outside_normal_overlay and height_ch.enable_subdiv_setup:
    #        for l in norm.outputs[0].links:
    #            mtree.links.remove(l)
    #    elif norm:
    #        for con in height_ch.ori_to:
    #            n = mtree.nodes.get(con.node)
    #            if n:
    #                s = n.inputs.get(con.socket)
    #                if s:
    #                    create_link(mtree, norm.outputs[0], s)

    # Remember active object
    ori_active_obj = bpy.context.object

    # Iterate all objects with same materials
    proportions = get_objs_size_proportions(objs)
    for obj in objs:

        # Set active object to modify modifier order
        set_active_object(obj)

        # Subsurf / Multires Modifier
        subsurf = get_subsurf_modifier(obj)
        multires = get_multires_modifier(obj, include_hidden=True)

        if multires:
            if height_ch.enable_subdiv_setup and (height_ch.subdiv_subsurf_only or height_ch.subdiv_adaptive):
                multires.show_render = False
                multires.show_viewport = False
            else:
                if subsurf: 
                    obj.modifiers.remove(subsurf)
                multires.show_render = True
                multires.show_viewport = True
                subsurf = multires

        if height_ch.enable_subdiv_setup:
            if not subsurf:
                subsurf = obj.modifiers.new('Subsurf', 'SUBSURF')
                if obj.type == 'MESH' and is_mesh_flat_shaded(obj.data):
                    subsurf.subdivision_type = 'SIMPLE'

            setup_subdiv_to_max_polys(obj, height_ch.subdiv_on_max_polys * 1000 * proportions[obj.name], subsurf)

        # Set subsurf to visible
        if subsurf:
            subsurf.show_render = True
            subsurf.show_viewport = True

        # Adaptive subdiv
        if height_ch.enable_subdiv_setup and height_ch.subdiv_adaptive:
            obj.cycles.use_adaptive_subdivision = True
        else: obj.cycles.use_adaptive_subdivision = False

    set_active_object(ori_active_obj)

def update_subdiv_setup(self, context):
    tree = self.id_data
    yp = tree.yp

    # Unset displacement node setup
    if not self.enable_subdiv_setup:
        mat = get_active_material()
        node = get_active_ypaint_node()
        check_displacement_node(mat, node, unset_one=True)

    # Check input and outputs
    check_all_channel_ios(yp, reconnect=False)

    # Check subdiv setup
    check_subdiv_setup(self)

    # Reconnect layers
    for layer in yp.layers:
        reconnect_layer_nodes(layer)
        rearrange_layer_nodes(layer)

    # Reconnect nodes
    reconnect_yp_nodes(tree)
    rearrange_yp_nodes(tree)

def remember_subsurf_levels():
    #print('Remembering')
    mat = get_active_material()
    objs = get_all_objects_with_same_materials(mat, True)

    for obj in objs:
        subsurf = get_subsurf_modifier(obj)
        if subsurf:
            obj.yp.ori_subsurf_render_levels = subsurf.render_levels
            obj.yp.ori_subsurf_levels = subsurf.levels

        multires = get_multires_modifier(obj)
        if multires:
            obj.yp.ori_multires_render_levels = multires.render_levels
            obj.yp.ori_multires_levels = multires.levels

def recover_subsurf_levels():
    #print('Recovering')
    mat = get_active_material()
    objs = get_all_objects_with_same_materials(mat, True)

    for obj in objs:
        subsurf = get_subsurf_modifier(obj)
        if subsurf:
            if subsurf.render_levels != obj.yp.ori_subsurf_render_levels:
                subsurf.render_levels = obj.yp.ori_subsurf_render_levels
            if subsurf.levels != obj.yp.ori_subsurf_levels:
                subsurf.levels = obj.yp.ori_subsurf_levels

        multires = get_multires_modifier(obj)
        if multires:
            render_levels = obj.yp.ori_multires_render_levels if obj.yp.ori_multires_render_levels <= multires.total_levels else multires.total_levels
            if multires.render_levels != render_levels:
                multires.render_levels = render_levels

            levels = obj.yp.ori_multires_levels if obj.yp.ori_multires_levels <= multires.total_levels else multires.total_levels
            if multires.levels != levels:
                multires.levels = levels

def update_enable_subdiv_setup(self, context):
    tree = self.id_data
    yp = tree.yp
    height_ch = self

    if height_ch.enable_subdiv_setup:
        remember_subsurf_levels()

    update_subdiv_setup(self, context)

    if not height_ch.enable_subdiv_setup:
        recover_subsurf_levels()

def setup_subdiv_to_max_polys(obj, max_polys, subsurf=None):
    
    if obj.type != 'MESH': return
    if not subsurf: subsurf = get_subsurf_modifier(obj)
    if not subsurf: return

    # Check object polygons
    num_poly = len(obj.data.polygons)

    # Get levels
    level = int(math.log(max_polys / num_poly, 4))

    if subsurf.type == 'MULTIRES':
        if level > subsurf.total_levels: 
            set_active_object(obj)
            for i in range(level - subsurf.total_levels):
                if not is_bl_newer_than(2, 90):
                    bpy.ops.object.multires_subdivide(modifier=subsurf.name)
                else:
                    if is_mesh_flat_shaded(obj.data):
                        bpy.ops.object.multires_subdivide(modifier=subsurf.name, mode='SIMPLE')
                    else: bpy.ops.object.multires_subdivide(modifier=subsurf.name, mode='CATMULL_CLARK')
            level = subsurf.total_levels
    else:
        # Maximum subdivision is 10
        if level > 10: level = 10

    subsurf.render_levels = level
    subsurf.levels = level

def get_objs_size_proportions(objs):

    sizes = []
    
    for obj in objs:
        sorted_dim = sorted(obj.dimensions, reverse=True)
        # Object size is only measured on its largest 2 dimensions because this should work on a plane too
        size = sorted_dim[0] * sorted_dim[1]
        sizes.append(size)

    total_size = sum(sizes)

    # Measure object size compared to total size
    proportions = {}
    for i, size in enumerate(sizes):
        proportions[objs[i].name] = size/total_size

    return proportions

def update_subdiv_max_polys(self, context):
    mat = get_active_material()
    tree = self.id_data
    yp = tree.yp
    ypup = get_user_preferences()
    height_ch = self
    objs = get_all_objects_with_same_materials(mat, True)

    #if not ypup.eevee_next_displacement and (not yp.use_baked or not height_ch.enable_subdiv_setup or self.subdiv_adaptive): return
    if not height_ch.enable_subdiv_setup: return

    proportions = get_objs_size_proportions(objs)

    for obj in objs:

        subsurf = get_subsurf_modifier(obj)
        multires = get_multires_modifier(obj)

        if multires and not height_ch.subdiv_subsurf_only:
            subsurf = multires 

        if not subsurf: continue

        setup_subdiv_to_max_polys(obj, height_ch.subdiv_on_max_polys * 1000 * proportions[obj.name], subsurf)

#def update_subdiv_standard_type(self, context):
#    obj = context.object
#    tree = self.id_data
#    yp = tree.yp
#
#    height_ch = self
#
#    subsurf = get_subsurf_modifier(obj)
#    if not subsurf: return
#
#    subsurf.subdivision_type = height_ch.subdiv_standard_type

def update_subdiv_global_dicing(self, context):
    scene = context.scene
    height_ch = self

    scene.cycles.dicing_rate = height_ch.subdiv_global_dicing
    scene.cycles.preview_dicing_rate = height_ch.subdiv_global_dicing

def register():
    bpy.utils.register_class(YTransferSomeLayerUV)
    bpy.utils.register_class(YTransferLayerUV)
    bpy.utils.register_class(YResizeImage)
    bpy.utils.register_class(YBakeChannels)
    bpy.utils.register_class(YBakeChannelToVcol)
    bpy.utils.register_class(YMergeLayer)
    bpy.utils.register_class(YMergeMask)
    bpy.utils.register_class(YBakeTempImage)
    bpy.utils.register_class(YDisableTempImage)
    bpy.utils.register_class(YDeleteBakedChannelImages)

def unregister():
    bpy.utils.unregister_class(YTransferSomeLayerUV)
    bpy.utils.unregister_class(YTransferLayerUV)
    bpy.utils.unregister_class(YResizeImage)
    bpy.utils.unregister_class(YBakeChannels)
    bpy.utils.unregister_class(YBakeChannelToVcol)
    bpy.utils.unregister_class(YMergeLayer)
    bpy.utils.unregister_class(YMergeMask)
    bpy.utils.unregister_class(YBakeTempImage)
    bpy.utils.unregister_class(YDisableTempImage)
    bpy.utils.unregister_class(YDeleteBakedChannelImages)
