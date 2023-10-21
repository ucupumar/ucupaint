import bpy, re, time, math, numpy
from bpy.props import *
from mathutils import *
from .common import *
from .bake_common import *
from .subtree import *
from .node_connections import *
from .node_arrangements import *
from . import lib, Layer, Mask, ImageAtlas, Modifier, MaskModifier

def transfer_uv(objs, mat, entity, uv_map):

    yp = entity.id_data.yp
    scene = bpy.context.scene

    # Check entity
    m1 = re.match(r'^yp\.layers\[(\d+)\]$', entity.path_from_id())
    m2 = re.match(r'^yp\.layers\[(\d+)\]\.masks\[(\d+)\]$', entity.path_from_id())

    if m1: 
        source = get_layer_source(entity)
        mapping = get_layer_mapping(entity)
        index = int(m1.group(1))
    elif m2: 
        source = get_mask_source(entity)
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
        elif m2: # Possible mask base color
            if index == 0:
                col = (0.0, 0.0, 0.0, 1.0)
            else:
                col = (1.0, 1.0, 1.0, 1.0)
        else:
            col = (0.0, 0.0, 0.0, 0.0)
            use_alpha = True

    # Create temp image as bake target
    if len(tilenums) > 1 or (segment and image.source == 'TILED'):
        temp_image = bpy.data.images.new(name='__TEMP',
                width=width, height=height, alpha=True, float_buffer=image.is_float, tiled=True)

        # Fill tiles
        for tilenum in tilenums:
            UDIM.fill_tile(temp_image, tilenum, col, width, height)

        # Initial pack
        if image.yua.is_udim_atlas:
            UDIM.initial_pack_udim(temp_image, col)
        else: UDIM.initial_pack_udim(temp_image, col, image.name)

    else:
        temp_image = bpy.data.images.new(name='__TEMP',
                width=width, height=height, alpha=True, float_buffer=image.is_float)

    #temp_image.colorspace_settings.name = 'Non-Color'
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

    if is_greater_than_281():
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
    mat.node_tree.links.new(src_uv.outputs[0], mapp.inputs[0])
    mat.node_tree.links.new(mapp.outputs[0], src.inputs[0])
    rgb = src.outputs[0]
    alpha = src.outputs[1]
    if straight_over:
        mat.node_tree.links.new(rgb, straight_over.inputs[2])
        mat.node_tree.links.new(alpha, straight_over.inputs[3])
        rgb = straight_over.outputs[0]

    mat.node_tree.links.new(rgb, emit.inputs[0])
    mat.node_tree.links.new(emit.outputs[0], output.inputs[0])

    # Bake!
    bpy.ops.object.bake()

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
        temp_image1.colorspace_settings.name = 'Non-Color'

        # Bake again!
        bpy.ops.object.bake()

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
        bpy.data.images.remove(temp_image1)

    if segment and image.source == 'TILED':

        # Remove original segment
        UDIM.remove_udim_atlas_segment_by_name(image, segment.name, yp)

        # Create new segment
        new_segment = UDIM.get_set_udim_atlas_segment(tilenums, 
                width=width, height=height, color=col, 
                colorspace=image.colorspace_settings.name, hdr=image.is_float, yp=yp, 
                source_image=temp_image, source_tilenums=tilenums)

        # Set image
        if image != new_segment.id_data:
            source.image = new_segment.id_data

        # Remove temp image
        bpy.data.images.remove(temp_image)

    elif temp_image.source == 'TILED' or image.source == 'TILED':
        # Replace image if any of the images is using UDIM
        replace_image(image, temp_image)
    else:
        # Copy back temp/baked image to original image
        copy_image_pixels(temp_image, image, segment)

        # Remove temp image
        bpy.data.images.remove(temp_image)

    # Remove temp nodes
    simple_remove_node(mat.node_tree, tex)
    simple_remove_node(mat.node_tree, emit)
    simple_remove_node(mat.node_tree, src)
    simple_remove_node(mat.node_tree, src_uv)
    simple_remove_node(mat.node_tree, mapp)
    if straight_over:
        simple_remove_node(mat.node_tree, straight_over)

    mat.node_tree.links.new(ori_bsdf, output.inputs[0])

    # Update entity transform
    entity.translation = (0.0, 0.0, 0.0)
    entity.rotation = (0.0, 0.0, 0.0)
    entity.scale = (1.0, 1.0, 1.0)

    # Change uv of entity
    entity.uv_name = uv_map

    # Update mapping
    update_mapping(entity)

    # Remove temporary objects
    if temp_objs:
        for o in temp_objs:
            m = o.data
            bpy.data.objects.remove(o)
            bpy.data.meshes.remove(m)

class YTransferSomeLayerUV(bpy.types.Operator):
    bl_idname = "node.y_transfer_some_layer_uv"
    bl_label = "Transfer Some Layer UV"
    bl_description = "Transfer some layers/masks UV by baking it to other uv (this will take quite some time to finish)"
    bl_options = {'REGISTER', 'UNDO'}

    from_uv_map : StringProperty(default='')
    uv_map : StringProperty(default='')
    uv_map_coll : CollectionProperty(type=bpy.types.PropertyGroup)

    samples : IntProperty(name='Bake Samples', 
            description='Bake Samples, more means less jagged on generated textures', 
            default=1, min=1)

    margin : IntProperty(name='Bake Margin',
            description = 'Bake margin in pixels',
            default=5, subtype='PIXEL')

    remove_from_uv : BoolProperty(name='Delete From UV',
            description = "Remove 'From UV' from objects",
            default=False)

    reorder_uv_list : BoolProperty(name='Reorder UV',
            description = "Reorder 'To UV' so it will have the same index as 'From UV'",
            default=True)

    @classmethod
    def poll(cls, context):
        return get_active_ypaint_node() and context.object.type == 'MESH' # and hasattr(context, 'layer')

    def invoke(self, context, event):

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

        if is_greater_than_280():
            row = self.layout.split(factor=0.4)
        else: row = self.layout.split(percentage=0.4)

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
        col.prop(self, 'margin', text='')
        col.prop(self, 'remove_from_uv')

        if self.remove_from_uv:
            col.prop(self, 'reorder_uv_list')

    def execute(self, context):

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
        prepare_bake_settings(book, objs, yp, samples=self.samples, margin=self.margin, 
                uv_map=self.uv_map, bake_type='EMIT', bake_device='CPU'
                )

        for layer in yp.layers:
            #print(layer.name)
            if layer.uv_name == self.from_uv_map:
                if layer.type == 'IMAGE':
                    print('TRANSFER UV: Transferring layer ' + layer.name + '...')
                    transfer_uv(objs, mat, layer, self.uv_map)
                else:
                    layer.uv_name = self.uv_map

            for mask in layer.masks:
                if mask.uv_name == self.from_uv_map:
                    if mask.type == 'IMAGE':
                        print('TRANSFER UV: Transferring mask ' + mask.name + ' on layer ' + layer.name + '...')
                        transfer_uv(objs, mat, mask, self.uv_map)
                        #return {'FINISHED'}
                    else:
                        mask.uv_name = self.uv_map

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

        print('INFO: All layer and masks that using', self.from_uv_map, 'is transferred to', self.uv_map, 'at', '{:0.2f}'.format(time.time() - T), 'seconds!')

        return {'FINISHED'}

class YTransferLayerUV(bpy.types.Operator):
    bl_idname = "node.y_transfer_layer_uv"
    bl_label = "Transfer Layer UV"
    bl_description = "Transfer Layer UV by baking it to other uv (this will take quite some time to finish)"
    bl_options = {'REGISTER', 'UNDO'}

    uv_map : StringProperty(default='')
    uv_map_coll : CollectionProperty(type=bpy.types.PropertyGroup)

    samples : IntProperty(name='Bake Samples', 
            description='Bake Samples, more means less jagged on generated textures', 
            default=1, min=1)

    margin : IntProperty(name='Bake Margin',
            description = 'Bake margin in pixels',
            default=5, subtype='PIXEL')

    @classmethod
    def poll(cls, context):
        return get_active_ypaint_node() and context.object.type == 'MESH' # and hasattr(context, 'layer')

    def invoke(self, context, event):
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
        if is_greater_than_280():
            row = self.layout.split(factor=0.4)
        else: row = self.layout.split(percentage=0.4)

        col = row.column(align=False)
        col.label(text='Target UV:')
        col.label(text='Samples:')
        col.label(text='Margin:')

        col = row.column(align=False)
        col.prop_search(self, "uv_map", self, "uv_map_coll", text='', icon='GROUP_UVS')
        col.prop(self, 'samples', text='')
        col.prop(self, 'margin', text='')

    def execute(self, context):
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
        prepare_bake_settings(book, objs, yp, samples=self.samples, margin=self.margin, 
                uv_map=self.uv_map, bake_type='EMIT', bake_device='CPU'
                )

        # Transfer UV
        transfer_uv(objs, mat, self.entity, self.uv_map)

        # Recover bake settings
        recover_bake_settings(book, yp)

        # Refresh mapping and stuff
        yp.active_layer_index = yp.active_layer_index

        print('INFO:', self.entity.name, 'UV is transferred from', self.entity.uv_name, 'to', self.uv_map, 'at', '{:0.2f}'.format(time.time() - T), 'seconds!')

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

class YResizeImage(bpy.types.Operator):
    bl_idname = "node.y_resize_image"
    bl_label = "Resize Image Layer/Mask"
    bl_description = "Resize image of layer or mask"
    bl_options = {'REGISTER', 'UNDO'}

    layer_name : StringProperty(default='')
    image_name : StringProperty(default='')

    width : IntProperty(name='Width', default = 1024, min=1, max=4096)
    height : IntProperty(name='Height', default = 1024, min=1, max=4096)

    samples : IntProperty(name='Bake Samples', 
            description='Bake Samples, more means less jagged on generated image', 
            default=1, min=1)

    all_tiles : BoolProperty(name='Resize All Tiles',
            description='Resize all tiles',
            default=False)

    tile_number : EnumProperty(name='Tile Number',
            description='Tile number that will be resized',
            items = UDIM.udim_tilenum_items,
            update=update_resize_image_tile_number)

    @classmethod
    def poll(cls, context):
        return get_active_ypaint_node() and context.object.type == 'MESH'

    def invoke(self, context, event):
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

        if is_greater_than_280():
            row = self.layout.split(factor=0.4)
        else: row = self.layout.split(percentage=0.4)

        col = row.column(align=False)

        col.label(text='Width:')
        col.label(text='Height:')

        if image:
            if image.yia.is_image_atlas or not is_greater_than_281():
                col.label(text='Samples:')

            if image.source == 'TILED':
                col.label(text='')
                if not self.all_tiles:
                    col.label(text='Tile Number:')

        col = row.column(align=False)

        col.prop(self, 'width', text='')
        col.prop(self, 'height', text='')

        if image:
            if image.yia.is_image_atlas or not is_greater_than_281():
                col.prop(self, 'samples', text='')

            if image.source == 'TILED':
                col.prop(self, 'all_tiles')
                if not self.all_tiles:
                    col.prop(self, 'tile_number', text='')

    def execute(self, context):

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

        if not image.yia.is_image_atlas and is_greater_than_281():

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
            scaled_img, new_segment = resize_image(image, self.width, self.height, image.colorspace_settings.name, self.samples, 0, segment, bake_device='CPU', yp=yp)

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

class YBakeChannelToVcol(bpy.types.Operator):
    """Bake Channel to Vertex Color"""
    bl_idname = "node.y_bake_channel_to_vcol"
    bl_label = "Bake channel to vertex color"
    bl_options = {'REGISTER', 'UNDO'}

    all_materials : BoolProperty(
            name='Bake All Materials',
            description='Bake all materials with ucupaint nodes rather than just the active one',
            default=False)

    vcol_name : StringProperty(
            name='Target Vertex Color Name', 
            description="Target vertex color name, it will create one if it doesn't exists",
            default='')
    
    add_emission : BoolProperty(
            name='Add Emission', 
            description='Add the result with Emission Channel', 
            default=False)

    emission_multiplier : FloatProperty(
            name='Emission Multiplier',
            description='Emission multiplier so the emission can be more visible on the result',
            default=1.0, min=0.0)

    force_first_index : BoolProperty(
            name='Force First Index', 
            description="Force target vertex color to be first on the vertex colors list (useful for exporting)",
            default=True)

    @classmethod
    def poll(cls, context):
        return get_active_ypaint_node() and context.object.type == 'MESH'

    def invoke(self, context, event):
        node = get_active_ypaint_node()
        yp = node.node_tree.yp
        channel = yp.channels[yp.active_channel_index]

        self.vcol_name = 'Baked ' + channel.name

        # Add emission will only availabel if it's on Color channel
        self.show_emission_option = False
        if channel.name == 'Color':
            for ch in yp.channels:
                if ch.name == 'Emission':
                    self.show_emission_option = True

        return context.window_manager.invoke_props_dialog(self, width=320)

    def check(self, context):
        return True

    def draw(self, context):
        if is_greater_than_280():
            row = self.layout.split(factor=0.4)
        else: row = self.layout.split(percentage=0.4)
        col = row.column(align=True)

        col.label(text='Target Vertex Color:')
        if self.show_emission_option:
            col.label(text='Add Emission:')
            col.label(text='Emission Multiplier:')

        if not is_version_320():
            col.label(text='Force First Index:')

        col = row.column(align=True)

        col.prop(self, 'vcol_name', text='')
        if self.show_emission_option:
            col.prop(self, 'add_emission', text='')
            col.prop(self, 'emission_multiplier', text='')
        if not is_version_320():
            col.prop(self, 'force_first_index', text='')

    def execute(self, context):
        if not is_greater_than_292():
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
                    if is_greater_than_280() and ob.hide_viewport: continue
                    #if not in_renderable_layer_collection(ob): continue
                    if len(ob.data.polygons) == 0: continue
                    for i, m in enumerate(ob.data.materials):
                        if m == mat:
                            ob.active_material_index = i
                            if ob not in objs and ob.data not in meshes:
                                objs.append(ob)
                                meshes.append(ob.data)

                if not objs: continue

                set_active_object(objs[i])

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
                    if self.force_first_index and not is_version_320():
                        move_vcol(ob, get_vcol_index(ob, vcol.name), 0)

                    # Get the newly created vcol to avoid pointer error
                    vcol = vcols.get(vcol_name)
                    set_active_vertex_color(ob, vcol)

                # Multi materials setup
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
                prepare_bake_settings(book, objs, yp, disable_problematic_modifiers=True, bake_device='CPU', bake_target='VERTEX_COLORS')

                # Get extra channel
                extra_channel = None
                if self.show_emission_option and self.add_emission:
                    extra_channel = yp.channels.get('Emission')

                # Bake channel
                bake_to_vcol(mat, node, channel, extra_channel, self.emission_multiplier)

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
    bl_idname = "node.y_delete_baked_channel_images"
    bl_label = "Delete All Baked Channel Images"
    bl_description = "Delete all baked channel images"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return get_active_ypaint_node() and context.object.type == 'MESH'

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=320)

    def draw(self, context):
        self.layout.label(text='Are you sure you want to delete all baked images?', icon='ERROR')

    def execute(self, context):
        node = get_active_ypaint_node()
        tree = node.node_tree
        yp = tree.yp

        # Set bake to false first
        if yp.use_baked:
            yp.use_baked = False

        # Remove baked nodes
        for root_ch in yp.channels:
            remove_node(tree, root_ch, 'baked')

            if root_ch.type == 'NORMAL':
                remove_node(tree, root_ch, 'baked_disp')
                remove_node(tree, root_ch, 'baked_normal_overlay')
                remove_node(tree, root_ch, 'baked_normal_prep')
                remove_node(tree, root_ch, 'baked_normal')

        # Reconnect
        rearrange_yp_nodes(tree)
        reconnect_yp_nodes(tree)

        return {'FINISHED'}

class YBakeChannels(bpy.types.Operator):
    """Bake Channels to Image(s)"""
    bl_idname = "node.y_bake_channels"
    bl_label = "Bake channels to Image"
    bl_options = {'REGISTER', 'UNDO'}

    width : IntProperty(name='Width', default = 1234, min=1, max=4096)
    height : IntProperty(name='Height', default = 1234, min=1, max=4096)

    uv_map : StringProperty(default='')
    uv_map_coll : CollectionProperty(type=bpy.types.PropertyGroup)

    samples : IntProperty(name='Bake Samples', 
            description='Bake Samples, more means less jagged on generated textures', 
            default=1, min=1)

    margin : IntProperty(name='Bake Margin',
            description = 'Bake margin in pixels',
            default=5, subtype='PIXEL')

    #hdr : BoolProperty(name='32 bit Float', default=False)

    fxaa : BoolProperty(name='Use FXAA', 
            description = "Use FXAA to baked images (doesn't work with float/non clamped images)",
            default=True)

    aa_level : IntProperty(
        name='Anti Aliasing Level',
        description='Super Sample Anti Aliasing Level (1=off)',
        default=1, min=1, max=2)

    force_bake_all_polygons : BoolProperty(
            name='Force Bake all Polygons',
            description='Force bake all polygons, useful if material is not using direct polygon (ex: solidify material)',
            default=False)

    bake_device : EnumProperty(
            name='Bake Device',
            description='Device to use for baking',
            items = (('GPU', 'GPU Compute', ''),
                     ('CPU', 'CPU', '')),
            default='CPU'
            )

    @classmethod
    def poll(cls, context):
        return get_active_ypaint_node() and context.object.type == 'MESH'

    def invoke(self, context, event):
        node = get_active_ypaint_node()
        yp = node.node_tree.yp
        obj = self.obj = context.object
        scene = context.scene
        ypup = get_user_preferences()

        # Use active uv layer name by default
        uv_layers = get_uv_layers(obj)

        # Use user preference default image size if input uses default image size
        if self.width == 1234 and self.height == 1234:
            self.width = self.height = ypup.default_new_image_size

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

        if len(yp.channels) > 0:
            for ch in yp.channels:
                baked = node.node_tree.nodes.get(ch.baked)
                if baked and baked.image:
                    self.width = baked.image.size[0]
                    self.height = baked.image.size[1]
                    break

        return context.window_manager.invoke_props_dialog(self, width=320)

    def check(self, context):
        return True

    def draw(self, context):
        obj = context.object
        mat = obj.active_material

        if is_greater_than_280():
            row = self.layout.split(factor=0.4)
        else: row = self.layout.split(percentage=0.4)
        col = row.column(align=True)

        col.label(text='Width:')
        col.label(text='Height:')
        #col.label(text='')
        col.separator()
        col.label(text='Samples:')
        col.label(text='Margin:')
        col.label(text='AA Level:')
        col.separator()
        if is_greater_than_280():
            col.label(text='Bake Device:')
            col.separator()
        col.label(text='UV Map:')
        col.separator()
        col.label(text='')
        col.label(text='')

        col = row.column(align=True)

        col.prop(self, 'width', text='')
        col.prop(self, 'height', text='')
        #col.prop(self, 'hdr')
        col.separator()

        col.prop(self, 'samples', text='')
        col.prop(self, 'margin', text='')
        col.prop(self, 'aa_level', text='')
        col.separator()

        if is_greater_than_280():
            col.prop(self, 'bake_device', text='')
            col.separator()
        col.prop_search(self, "uv_map", self, "uv_map_coll", text='', icon='GROUP_UVS')
        col.separator()
        col.prop(self, 'fxaa', text='Use FXAA')
        col.prop(self, 'force_bake_all_polygons')

    def execute(self, context):

        T = time.time()

        node = get_active_ypaint_node()
        tree = node.node_tree
        yp = tree.yp
        scene = context.scene
        obj = context.object
        mat = obj.active_material

        if is_greater_than_280() and (obj.hide_viewport or obj.hide_render):
            self.report({'ERROR'}, "Please unhide render and viewport of active object!")
            return {'CANCELLED'}

        if not is_greater_than_280() and obj.hide_render:
            self.report({'ERROR'}, "Please unhide render of active object!")
            return {'CANCELLED'}

        book = remember_before_bake(yp)

        height_ch = get_root_height_channel(yp)

        tangent_sign_calculation = False
        if BL28_HACK and height_ch and is_greater_than_280() and not is_greater_than_300():

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

        #return {'FINISHED'}

        # Disable use baked first
        if yp.use_baked:
            yp.use_baked = False

        # Get all objects using material
        objs = [obj]
        meshes = [obj.data]
        if mat.users > 1:
            # Emptying the lists again in case active object is problematic
            objs = []
            meshes = []
            for ob in get_scene_objects():
                if ob.type != 'MESH': continue
                if is_greater_than_280() and ob.hide_viewport: continue
                if ob.hide_render: continue
                if not in_renderable_layer_collection(ob): continue
                if len(get_uv_layers(ob)) == 0: continue
                if len(ob.data.polygons) == 0: continue
                for i, m in enumerate(ob.data.materials):
                    if m == mat:
                        ob.active_material_index = i
                        if ob not in objs and ob.data not in meshes:
                            objs.append(ob)
                            meshes.append(ob.data)

        # Multi materials setup
        ori_mat_ids = {}
        ori_loop_locs = {}
        for ob in objs:

            # Get uv map
            uv_layers = get_uv_layers(ob)
            uvl = uv_layers.get(self.uv_map)

            # Need to assign all polygon to active material if there are multiple materials
            ori_mat_ids[ob.name] = []
            ori_loop_locs[ob.name] = []

            if len(ob.data.materials) > 1:

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
        prepare_bake_settings(book, objs, yp, self.samples, margin, self.uv_map, disable_problematic_modifiers=True, bake_device=self.bake_device)

        # Bake channels
        for ch in yp.channels:
            ch.no_layer_using = not is_any_layer_using_channel(ch, node)
            if not ch.no_layer_using:
                #if ch.type != 'NORMAL': continue
                use_hdr = not ch.use_clamp
                bake_channel(self.uv_map, mat, node, ch, width, height, use_hdr=use_hdr)

        # AA process
        if self.aa_level > 1:
            for ch in yp.channels:

                baked = tree.nodes.get(ch.baked)
                if baked and baked.image:
                    resize_image(baked.image, self.width, self.height, 
                            baked.image.colorspace_settings.name, alpha_aware=ch.enable_alpha, bake_device=self.bake_device)

                if ch.type == 'NORMAL':

                    baked_disp = tree.nodes.get(ch.baked_disp)
                    if baked_disp and baked_disp.image:
                        resize_image(baked_disp.image, self.width, self.height, 
                                baked.image.colorspace_settings.name, alpha_aware=ch.enable_alpha, bake_device=self.bake_device)

                    baked_normal_overlay = tree.nodes.get(ch.baked_normal_overlay)
                    if baked_normal_overlay and baked_normal_overlay.image:
                        resize_image(baked_normal_overlay.image, self.width, self.height, 
                                baked.image.colorspace_settings.name, alpha_aware=ch.enable_alpha, bake_device=self.bake_device)

        # FXAA
        if self.fxaa:
            for ch in yp.channels:
                # FXAA doesn't work with hdr image
                if not ch.use_clamp: continue

                baked = tree.nodes.get(ch.baked)
                if baked and baked.image:
                    fxaa_image(baked.image, ch.enable_alpha, bake_device=self.bake_device)

                if ch.type == 'NORMAL':

                    baked_disp = tree.nodes.get(ch.baked_disp)
                    if baked_disp and baked_disp.image:
                        fxaa_image(baked_disp.image, ch.enable_alpha, bake_device=self.bake_device)

                    baked_normal_overlay = tree.nodes.get(ch.baked_normal_overlay)
                    if baked_normal_overlay and baked_normal_overlay.image:
                        fxaa_image(baked_normal_overlay.image, ch.enable_alpha, bake_device=self.bake_device)

        # Set baked uv
        yp.baked_uv_name = self.uv_map

        # Recover bake settings
        recover_bake_settings(book, yp)

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
                            #print(ori_loop_locs[ob.name][i][j])
                            uvl.data[li].uv = ori_loop_locs[ob.name][i][j]

        # Use bake results
        yp.halt_update = True
        yp.use_baked = True
        yp.halt_update = False

        # Check subdiv Setup
        if height_ch:
            check_subdiv_setup(height_ch)

        # Update global uv
        check_uv_nodes(yp)

        # Recover hack
        if BL28_HACK and height_ch and tangent_sign_calculation and is_greater_than_280() and not is_greater_than_300():
            print('INFO: Recovering tangent sign after bake...')
            # Refresh tangent sign hacks
            update_enable_tangent_sign_hacks(yp, context)

        # Rearrange
        rearrange_yp_nodes(tree)
        reconnect_yp_nodes(tree)

        # Refresh active channel index
        yp.active_channel_index = yp.active_channel_index

        # Update baked outside nodes
        update_enable_baked_outside(yp, context)

        # Remove temporary objects
        if temp_objs:
            for o in temp_objs:
                m = o.data
                bpy.data.objects.remove(o)
                bpy.data.meshes.remove(m)

        print('INFO:', tree.name, 'channels is baked at', '{:0.2f}'.format(time.time() - T), 'seconds!')

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
        if hasattr(lib, 'custom_icons'):
            icon_name = lib.channel_custom_icon_dict[ch.type]
            items.append((str(i), ch.name, '', lib.custom_icons[icon_name].icon_id, counter))
        else: items.append((str(i), ch.name, '', lib.channel_icon_dict[ch.type], counter))
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

class YMergeLayer(bpy.types.Operator):
    bl_idname = "node.y_merge_layer"
    bl_label = "Merge layer"
    bl_description = "Merge Layer"
    bl_options = {'REGISTER', 'UNDO'}

    direction : EnumProperty(
            name = 'Direction',
            items = (('UP', 'Up', ''),
                     ('DOWN', 'Down', '')),
            default = 'UP')

    channel_idx : EnumProperty(
            name = 'Channel',
            description = 'Channel for merge reference',
            items = merge_channel_items)
            #update=update_channel_idx_new_layer)

    apply_modifiers : BoolProperty(
            name = 'Apply Layer Modifiers',
            description = 'Apply layer modifiers',
            default = False)

    apply_neighbor_modifiers : BoolProperty(
            name = 'Apply Neighbor Modifiers',
            description = 'Apply neighbor modifiers',
            default = True)

    #height_aware : BoolProperty(
    #        name = 'Height Aware',
    #        description = 'Height will take account for merge',
    #        default = True)

    @classmethod
    def poll(cls, context):
        group_node = get_active_ypaint_node()
        return (context.object and group_node and len(group_node.node_tree.yp.layers) > 0 
                and len(group_node.node_tree.yp.channels) > 0)

    def invoke(self, context, event):
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

        return context.window_manager.invoke_props_dialog(self, width=320)

    def draw(self, context):
        #col = self.layout.column()
        if is_greater_than_280():
            row = self.layout.split(factor=0.5)
        else: row = self.layout.split(percentage=0.5)

        col = row.column(align=False)
        col.label(text='Main Channel:')
        col.label(text='Apply Modifiers:')
        col.label(text='Apply Neighbor Modifiers:')

        col = row.column(align=False)
        col.prop(self, 'channel_idx', text='')
        col.prop(self, 'apply_modifiers', text='')
        col.prop(self, 'apply_neighbor_modifiers', text='')

    def execute(self, context):
        T = time.time()

        wm = context.window_manager
        node = get_active_ypaint_node()
        tree = node.node_tree
        yp = tree.yp
        obj = context.object
        mat = obj.active_material
        scene = context.scene
        objs = get_all_objects_with_same_materials(mat, True)

        if self.error_message != '':
            self.report({'ERROR'}, self.error_message)
            return {'CANCELLED'}

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

        # Get max height
        if height_root_ch and main_ch.type == 'NORMAL':
            end_max_height = tree.nodes.get(height_root_ch.end_max_height)
            ori_max_height = 0.0
            max_height = 0.0
            if end_max_height:
                ori_max_height = end_max_height.outputs[0].default_value
                max_height = get_max_height_from_list_of_layers([layer, neighbor_layer], int(self.channel_idx))
                end_max_height.outputs[0].default_value = max_height

        # Check layer
        if (layer.type == 'IMAGE' and layer.texcoord_type == 'UV'): # and neighbor_layer.type == 'IMAGE'):

            book = remember_before_bake(yp)
            prepare_bake_settings(book, objs, yp, samples=1, margin=5, 
                    uv_map=layer.uv_name, bake_type='EMIT' 
                    )

            #yp.halt_update = True

            # Ge list of parent ids
            #pids = get_list_of_parent_ids(layer)

            # Disable other layers
            #layer_oris = []
            #for i, l in enumerate(yp.layers):
            #    layer_oris.append(l.enable)
            #    #if i in pids:
            #    #    l.enable = True
            #    if l not in {layer, neighbor_layer}:
            #        l.enable = False

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

            #yp.halt_update = False

            # Enable alpha on main channel (will also update all the nodes)
            ori_enable_alpha = main_ch.enable_alpha
            yp.alpha_auto_setup = False
            main_ch.enable_alpha = True

            # Reconnect tree with merged layer ids
            reconnect_yp_nodes(tree, [layer_idx, neighbor_idx])

            # Bake main channel
            merge_success = bake_channel(layer.uv_name, mat, node, main_ch, target_layer=layer)
            #return {'FINISHED'}

            # Recover bake settings
            recover_bake_settings(book, yp)

            if not self.apply_modifiers:
                recover_layer_modifiers_and_transforms(layer, mod_oris)
            else: remove_layer_modifiers_and_transforms(layer)

            # Recover layer enable
            #for i, le in enumerate(layer_oris):
            #    if yp.layers[i].enable != le:
            #        yp.layers[i].enable = le

            # Recover original props
            main_ch.enable_alpha = ori_enable_alpha
            yp.alpha_auto_setup = True
            if main_ch.type != 'NORMAL':
                ch.blend_type = ori_blend_type
            else: ch.normal_blend_type = ori_blend_type

        #elif (layer.type == 'COLOR' and neighbor_layer.type == 'COLOR' 
        #        and len(layer.masks) != 0 and len(neighbor_layer.masks) == len(layer.masks)):
        #    pass
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

                    cols = numpy.zeros(len(obj.data.loops)*4, dtype=numpy.float32)
                    cols.shape = (cols.shape[0]//4, 4)

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

            #neighbor_layer.enable = False
            merge_success = True

        else:
            self.report({'ERROR'}, "This kind of merge is not supported yet!")
            return {'CANCELLED'}

        # Recover max height
        if height_root_ch and main_ch.type == 'NORMAL':
            if end_max_height: end_max_height.outputs[0].default_value = ori_max_height

        if merge_success:
            # Remove neighbor layer
            Layer.remove_layer(yp, neighbor_idx)

            if height_ch and main_ch.type == 'NORMAL' and height_ch.normal_map_type == 'BUMP_MAP':
                height_ch.bump_distance = max_height

            rearrange_yp_nodes(tree)
            reconnect_yp_nodes(tree)

            # Refresh index routine
            yp.active_layer_index = min(layer_idx, neighbor_idx)
        else:
            self.report({'ERROR'}, "Merge failed for some reason!")
            return {'CANCELLED'}

        return {'FINISHED'}

class YMergeMask(bpy.types.Operator):
    bl_idname = "node.y_merge_mask"
    bl_label = "Merge mask"
    bl_description = "Merge Mask"
    bl_options = {'REGISTER', 'UNDO'}

    direction : EnumProperty(
            name = 'Direction',
            items = (('UP', 'Up', ''),
                     ('DOWN', 'Down', '')),
            default = 'UP')

    @classmethod
    def poll(cls, context):
        return get_active_ypaint_node() and hasattr(context, 'mask') and hasattr(context, 'layer')

    def execute(self, context):
        mask = context.mask
        layer = context.layer
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
            neighbor_idx = index-1
        elif self.direction == 'DOWN' and index < num_masks-1:
            neighbor_idx = index+1
        else:
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

            img = bpy.data.images.new(name='__TEMP',
                    width=width, height=height, alpha=True, float_buffer=source.image.is_float)

            if source.image.yia.color == 'WHITE':
                img.generated_color = (1.0, 1.0, 1.0, 1.0)
            elif source.image.yia.color == 'BLACK':
                img.generated_color = (0.0, 0.0, 0.0, 1.0)
            else: img.generated_color = (0.0, 0.0, 0.0, 0.0)

            img.colorspace_settings.name = 'Non-Color'
        else:
            img = source.image.copy()
            width = img.size[0]
            height = img.size[1]

        # Activate layer preview mode
        ori_layer_preview_mode = yp.layer_preview_mode
        yp.layer_preview_mode = True

        # Get neighbor mask
        neighbor_mask = layer.masks[neighbor_idx]

        # Disable modifiers
        #ori_mods = []
        #for i, mod in enumerate(mask.modifiers):
        #    ori_mods.append(mod.enable)
        #    mod.enable = False

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
        rearrange_layer_nodes(layer)
        reconnect_layer_nodes(layer, merge_mask=True)

        # Prepare to bake
        objs = get_all_objects_with_same_materials(mat, True)

        book = remember_before_bake(yp)
        prepare_bake_settings(book, objs, yp, samples=1, margin=5, 
                uv_map=mask.uv_name, bake_type='EMIT'
                )

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
        bpy.ops.object.bake()

        # Copy results to original image
        copy_image_pixels(img, source.image, segment)

        # Remove temp image
        bpy.data.images.remove(img)

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

class YBakeTempImage(bpy.types.Operator):
    bl_idname = "node.y_bake_temp_image"
    bl_label = "Bake temporary image of layer"
    bl_description = "Bake temporary image of layer, can be useful to prefent glitch on cycles"
    bl_options = {'REGISTER', 'UNDO'}

    uv_map : StringProperty(default='')
    uv_map_coll : CollectionProperty(type=bpy.types.PropertyGroup)

    samples : IntProperty(name='Bake Samples', 
            description='Bake Samples, more means less jagged on generated textures', 
            default=1, min=1)

    margin : IntProperty(name='Bake Margin',
            description = 'Bake margin in pixels',
            default=5, subtype='PIXEL')

    width : IntProperty(name='Width', default = 1234, min=1, max=4096)
    height : IntProperty(name='Height', default = 1234, min=1, max=4096)

    hdr : BoolProperty(name='32 bit Float', default=True)

    @classmethod
    def poll(cls, context):
        return get_active_ypaint_node() #and hasattr(context, 'parent')

    def invoke(self, context, event):
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

        # Use user preference default image size if input uses default image size
        if self.width == 1234 and self.height == 1234:
            self.width = self.height = ypup.default_new_image_size

        return context.window_manager.invoke_props_dialog(self, width=320)

    def draw(self, context):
        node = get_active_ypaint_node()
        yp = node.node_tree.yp

        if is_greater_than_280():
            row = self.layout.split(factor=0.4)
        else: row = self.layout.split(percentage=0.4)

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
        col.prop(self, 'margin', text='')

    def execute(self, context):

        if not hasattr(self, 'parent'):
            self.report({'ERROR'}, "Context is incorrect!")
            return {'CANCELLED'}

        entity = self.parent
        if entity.type not in {'HEMI'}:
            self.report({'ERROR'}, "This layer type is not supported (yet)!")
            return {'CANCELLED'}

        # Bake temp image
        image = temp_bake(context, entity, self.width, self.height, self.hdr, self.samples , self.margin, self.uv_map)

        return {'FINISHED'}

class YDisableTempImage(bpy.types.Operator):
    bl_idname = "node.y_disable_temp_image"
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
        avg = sum([inp_source.default_value[i] for i in range(3)])/3
        inp_target.default_value = avg
    elif isinstance(inp_source.default_value, float):
        for i in range(3):
            inp_target.default_value[i] = inp_source.default_value

def update_enable_baked_outside(self, context):
    tree = self.id_data
    yp = tree.yp
    node = get_active_ypaint_node()
    mat = get_active_material()
    scene = context.scene

    mtree = mat.node_tree

    if yp.halt_update: return
    #if not yp.use_baked: return

    if yp.enable_baked_outside and yp.use_baked:

        # Delete disp node if available
        disp = get_adaptive_displacement_node(mat, node)
        if disp: simple_remove_node(mat.node_tree, disp)

        # Shift nodes to the right
        shift_nodes = []
        for n in mtree.nodes:
            if n.location.x > node.location.x:
                shift_nodes.append(n)
                #n.location.x += 600

        # Baked outside nodes should be contained inside of frame
        frame = mtree.nodes.get(yp.baked_outside_frame)
        if not frame:
            frame = mtree.nodes.new('NodeFrame')
            #frame.label = get_addon_title() + ' Baked Textures'
            frame.label = node.name + 'Baked Textures'
            frame.name = node.name + 'Baked Textures'
            yp.baked_outside_frame = frame.name

        loc_x = node.location.x + 180
        loc_y = node.location.y

        uv = check_new_node(mtree, yp, 'baked_outside_uv', 'ShaderNodeUVMap')
        #uv = mtree.nodes.new('ShaderNodeUVMap')
        uv.uv_map = yp.baked_uv_name
        uv.location.x = loc_x
        uv.location.y = loc_y
        uv.parent = frame
        #yp.baked_outside_uv = uv.name

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

            outp_alpha = node.outputs.get(ch.name + io_suffix['ALPHA'])
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
                mtree.links.new(uv.outputs[0], tex.inputs[0])

                if not is_greater_than_280() and baked.image.colorspace_settings.name != 'sRGB':
                    tex.color_space = 'NONE'

                if outp_alpha:
                    for l in outp_alpha.links:
                        mtree.links.new(tex.outputs[1], l.to_socket)

                if ch.type != 'NORMAL':

                    for l in outp.links:
                        mtree.links.new(tex.outputs[0], l.to_socket)

                else:

                    loc_x += 280
                    norm = check_new_node(mtree, ch, 'baked_outside_normal_process', 'ShaderNodeNormalMap')
                    norm.uv_map = yp.baked_uv_name
                    norm.location.x = loc_x
                    norm.location.y = loc_y
                    norm.parent = frame
                    max_x = loc_x
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

                            if not is_greater_than_280() and baked_normal_overlay.image.colorspace_settings.name != 'sRGB':
                                tex_normal_overlay.color_space = 'NONE'

                            if ch.enable_subdiv_setup and not ch.subdiv_adaptive:
                                mtree.links.new(tex_normal_overlay.outputs[0], norm.inputs[1])

                    if not ch.enable_subdiv_setup or baked_normal_overlay:
                        for l in outp.links:
                            mtree.links.new(norm.outputs[0], l.to_socket)

                    baked_disp = tree.nodes.get(ch.baked_disp)
                    if baked_disp and baked_disp.image:
                        loc_y -= 300
                        tex_disp = check_new_node(mtree, ch, 'baked_outside_disp', 'ShaderNodeTexImage')
                        tex_disp.image = baked_disp.image
                        tex_disp.location.x = loc_x
                        tex_disp.location.y = loc_y
                        tex_disp.parent = frame
                        mtree.links.new(uv.outputs[0], tex_disp.inputs[0])

                        if not is_greater_than_280() and baked_disp.image.colorspace_settings.name != 'sRGB':
                            tex_disp.color_space = 'NONE'

                        loc_x += 280
                        disp = mtree.nodes.get(ch.baked_outside_disp_process)
                        if is_greater_than_280():
                            if not disp:
                                disp = mtree.nodes.new('ShaderNodeDisplacement')
                            disp.inputs['Scale'].default_value = get_displacement_max_height(ch) * ch.subdiv_tweak
                        else:
                            if not disp:
                                disp = mat.node_tree.nodes.new('ShaderNodeGroup')
                                disp.node_tree = get_node_tree_lib(lib.BL27_DISP)
                            disp.inputs[1].default_value = get_displacement_max_height(ch) * ch.subdiv_tweak

                        disp.location.x = loc_x
                        disp.location.y = loc_y
                        disp.parent = frame
                        ch.baked_outside_disp_process = disp.name
                        max_x = loc_x
                        loc_x -= 280

                        mtree.links.new(tex_disp.outputs[0], disp.inputs[0])

                        output_mat = [n for n in mtree.nodes if n.type == 'OUTPUT_MATERIAL' and n.is_active_output]
                        if output_mat and ch.enable_subdiv_setup and ch.subdiv_adaptive:
                            mtree.links.new(disp.outputs[0], output_mat[0].inputs['Displacement'])

                loc_y -= 300

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

        for ch in yp.channels:

            outp = node.outputs.get(ch.name)
            connect_to_original_node(mtree, outp, ch.ori_to)
            ch.ori_to.clear()

            outp_alpha = node.outputs.get(ch.name + io_suffix['ALPHA'])
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
                remove_node(mtree, ch, 'baked_outside_disp', parent=baked_outside_frame)
                remove_node(mtree, ch, 'baked_outside_normal_overlay', parent=baked_outside_frame)
                remove_node(mtree, ch, 'baked_outside_normal_process', parent=baked_outside_frame)
                remove_node(mtree, ch, 'baked_outside_disp_process', parent=baked_outside_frame)

        if baked_outside_frame:
            remove_node(mtree, yp, 'baked_outside_uv', parent=baked_outside_frame)
            remove_node(mtree, yp, 'baked_outside_frame')

        # Shift back nodes location
        for n in mtree.nodes:
            if n.location.x > node.location.x:
                n.location.x -= yp.baked_outside_x_shift
        yp.baked_outside_x_shift = 0

        # Set back adaptive displacement node
        height_ch = get_root_height_channel(yp)
        if yp.use_baked and height_ch and height_ch.enable_subdiv_setup and height_ch.subdiv_adaptive:

            # Adaptive subdivision only works for experimental feature set for now
            scene.cycles.feature_set = 'EXPERIMENTAL'
            scene.cycles.dicing_rate = height_ch.subdiv_global_dicing
            scene.cycles.preview_dicing_rate = height_ch.subdiv_global_dicing

            set_adaptive_displacement_node(mat, node)

    #print("howowowo")

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

    if yp.halt_update: return

    # Check subdiv setup
    height_ch = get_root_height_channel(yp)
    if height_ch:
        if height_ch.enable_subdiv_setup and yp.use_baked:
            remember_subsurf_levels()
        check_subdiv_setup(height_ch)
        if height_ch.enable_subdiv_setup and not yp.use_baked:
            recover_subsurf_levels()

    # Check uv nodes
    check_uv_nodes(yp)

    # Reconnect nodes
    rearrange_yp_nodes(tree)
    reconnect_yp_nodes(tree)

    # Trigger active image update
    if self.use_baked:
        self.active_channel_index = self.active_channel_index
    else:
        self.active_layer_index = self.active_layer_index

    # Update baked outside
    update_enable_baked_outside(self, context)

def set_adaptive_displacement_node(mat, node):
    return get_adaptive_displacement_node(mat, node, set_one=True)

def get_adaptive_displacement_node(mat, node, set_one=False):

    try: output_mat = [n for n in mat.node_tree.nodes if n.type == 'OUTPUT_MATERIAL' and n.is_active_output][0]
    except: return None

    height_ch = get_root_height_channel(node.node_tree.yp)
    if not height_ch: return None

    disp = None

    # Check output connection
    norm_outp = node.outputs[height_ch.name]
    height_outp = node.outputs[height_ch.name + io_suffix['HEIGHT']]
    max_height_outp = node.outputs[height_ch.name + io_suffix['MAX_HEIGHT']]
    disp_mat_inp = output_mat.inputs['Displacement']

    if is_greater_than_280():
        # Search for displacement node
        height_matches = []
        for link in height_outp.links:
            if link.to_node.type == 'DISPLACEMENT':
                #disp = link.to_node
                height_matches.append(link.to_node)

        max_height_matches = []
        for link in max_height_outp.links:
            if link.to_node.type == 'DISPLACEMENT':
                max_height_matches.append(link.to_node)

    else:
        # Search for displacement node
        height_matches = []
        for link in height_outp.links:
            #if link.to_node.type == 'MATH' and link.to_node.operation == 'MULTIPLY':
            if link.to_node.type == 'GROUP' and link.to_node.node_tree.name == lib.BL27_DISP:
                #disp = link.to_node
                height_matches.append(link.to_node)

        max_height_matches = []
        for link in max_height_outp.links:
            #if link.to_node.type == 'MATH' and link.to_node.operation == 'MULTIPLY':
            if link.to_node.type == 'GROUP' and link.to_node.node_tree.name == lib.BL27_DISP:
                max_height_matches.append(link.to_node)

    for n in height_matches:
        if n in max_height_matches and any([l for l in disp_mat_inp.links if l.from_node == n]):
            disp = n
            break

    if set_one and not disp:
        if is_greater_than_280():
            #mat.cycles.displacement_method = 'BOTH'
            #mat.cycles.displacement_method = 'DISPLACEMENT'

            disp = mat.node_tree.nodes.new('ShaderNodeDisplacement')
            disp.location.x = node.location.x #+ 200
            disp.location.y = node.location.y - 400

            create_link(mat.node_tree, disp.outputs[0], output_mat.inputs['Displacement'])
            create_link(mat.node_tree, height_outp, disp.inputs['Height'])
            create_link(mat.node_tree, max_height_outp, disp.inputs['Scale'])
        else:
            # Remember normal connection, because it will be disconnected to avoid render error
            for link in norm_outp.links:
                con = height_ch.ori_normal_to.add()
                con.node = link.to_node.name
                con.socket = link.to_socket.name

            # Remove normal connection because it will produce render error
            break_output_link(mat.node_tree, norm_outp)

            # Set displacement mode
            #mat.cycles.displacement_method = 'BOTH'
            #mat.cycles.displacement_method = 'TRUE'

            #disp = mat.node_tree.nodes.new('ShaderNodeMath')
            #disp.operation = 'MULTIPLY'
            disp = mat.node_tree.nodes.new('ShaderNodeGroup')
            disp.node_tree = get_node_tree_lib(lib.BL27_DISP)
            disp.location.x = node.location.x #+ 200
            disp.location.y = node.location.y - 400

            create_link(mat.node_tree, disp.outputs[0], output_mat.inputs['Displacement'])
            create_link(mat.node_tree, height_outp, disp.inputs[0])
            create_link(mat.node_tree, max_height_outp, disp.inputs[1])

    return disp

def check_subdiv_setup(height_ch):
    tree = height_ch.id_data
    yp = tree.yp

    if not height_ch: return
    #obj = bpy.context.object
    mat = get_active_material()
    scene = bpy.context.scene

    mtree = mat.node_tree

    # Get height image and max height
    baked_disp = tree.nodes.get(height_ch.baked_disp)
    end_max_height = tree.nodes.get(height_ch.end_max_height)
    if not baked_disp or not baked_disp.image or not end_max_height: return
    img = baked_disp.image
    max_height = end_max_height.outputs[0].default_value

    # Max height tweak node
    if yp.use_baked and height_ch.enable_subdiv_setup:
        end_max_height = check_new_node(tree, height_ch, 'end_max_height_tweak', 'ShaderNodeMath', 'Max Height Tweak')
        end_max_height.operation = 'MULTIPLY'
        end_max_height.inputs[1].default_value = height_ch.subdiv_tweak
    else:
        remove_node(tree, height_ch, 'end_max_height_tweak')

    # Get active output material
    try: output_mat = [n for n in mtree.nodes if n.type == 'OUTPUT_MATERIAL' and n.is_active_output][0]
    except: return

    # Get active ypaint node
    node = get_active_ypaint_node()
    norm_outp = node.outputs[height_ch.name]

    # Recover normal for Blender 2.7
    if not is_greater_than_280():

        if not yp.use_baked or not height_ch.enable_subdiv_setup or (
                height_ch.enable_subdiv_setup and not height_ch.subdiv_adaptive):

            # Relink will only be proceed if no new links found
            link_found = any([l for l in norm_outp.links])
            if not link_found:

                # Try to relink to original connections
                for con in height_ch.ori_normal_to:
                    try:
                        node_to = mtree.nodes.get(con.node)
                        socket_to = node_to.inputs[con.socket]
                        if len(socket_to.links) < 1:
                            mtree.links.new(norm_outp, socket_to)
                    except: pass
                
            height_ch.ori_normal_to.clear()

    # Adaptive subdiv
    if yp.use_baked and height_ch.enable_subdiv_setup and height_ch.subdiv_adaptive: #and not yp.enable_baked_outside:

        # Adaptive subdivision only works for experimental feature set for now
        scene.cycles.feature_set = 'EXPERIMENTAL'
        scene.cycles.dicing_rate = height_ch.subdiv_global_dicing
        scene.cycles.preview_dicing_rate = height_ch.subdiv_global_dicing

        # Set displacement mode
        if is_greater_than_280():
            mat.cycles.displacement_method = 'DISPLACEMENT'
        else: mat.cycles.displacement_method = 'TRUE'

        if not yp.enable_baked_outside:
            set_adaptive_displacement_node(mat, node)

    else:
        disp = get_adaptive_displacement_node(mat, node)
        if disp: simple_remove_node(mtree, disp)

        # Back to supported feature set
        #scene.cycles.feature_set = 'SUPPORTED'

        # Remove displacement output material link
        # NOTE: It's very forced, but whatever
        #break_input_link(mtree, output_mat.inputs['Displacement'])

    # Outside nodes connection set
    if yp.use_baked and yp.enable_baked_outside:
        frame = get_node(mtree, yp.baked_outside_frame)
        norm = get_node(mtree, height_ch.baked_outside_normal_process, parent=frame)
        disp = get_node(mtree, height_ch.baked_outside_disp_process, parent=frame)
        baked_outside = get_node(mtree, height_ch.baked_outside, parent=frame)
        baked_outside_normal_overlay = get_node(mtree, height_ch.baked_outside_normal_overlay, parent=frame)

        if height_ch.enable_subdiv_setup:
            if height_ch.subdiv_adaptive:
                if disp:
                    create_link(mtree, disp.outputs[0], output_mat.inputs['Displacement'])
                if baked_outside and norm:
                    create_link(mtree, baked_outside.outputs[0], norm.inputs[1])
            else:
                if disp:
                    break_link(mtree, disp.outputs[0], output_mat.inputs['Displacement'])
                if baked_outside_normal_overlay and norm:
                    create_link(mtree, baked_outside_normal_overlay.outputs[0], norm.inputs[1])
        else:
            if baked_outside and norm:
                create_link(mtree, baked_outside.outputs[0], norm.inputs[1])
        
        if norm and not baked_outside_normal_overlay and height_ch.enable_subdiv_setup and not height_ch.subdiv_adaptive:
            for l in norm.outputs[0].links:
                mtree.links.remove(l)
        elif norm:
            for con in height_ch.ori_to:
                n = mtree.nodes.get(con.node)
                if n:
                    s = n.inputs.get(con.socket)
                    if s:
                        create_link(mtree, norm.outputs[0], s)

    # Remember active object
    ori_active_obj = bpy.context.object

    # Iterate all objects with same materials
    objs = get_all_objects_with_same_materials(mat, True)
    proportions = get_objs_size_proportions(objs)
    for obj in objs:

        # Set active object to modify modifier order
        set_active_object(obj)

        # Subsurf / Multires Modifier
        subsurf = get_subsurf_modifier(obj)
        multires = get_multires_modifier(obj)

        #if yp.use_baked and height_ch.enable_subdiv_setup and multires:
        if multires:
            if yp.use_baked and height_ch.enable_subdiv_setup and (height_ch.subdiv_subsurf_only or height_ch.subdiv_adaptive):
                multires.show_render = False
                multires.show_viewport = False
            else:
                if subsurf: 
                    obj.modifiers.remove(subsurf)
                multires.show_render = True
                multires.show_viewport = True
                subsurf = multires

        if yp.use_baked and height_ch.enable_subdiv_setup and not height_ch.subdiv_adaptive:

            if not subsurf:
                
                subsurf = obj.modifiers.new('Subsurf', 'SUBSURF')
                if obj.type == 'MESH' and is_mesh_flat_shaded(obj.data):
                    subsurf.subdivision_type = 'SIMPLE'

            #obj.yp.ori_subsurf_render_levels = subsurf.render_levels
            #obj.yp.ori_subsurf_levels = subsurf.levels

            setup_subdiv_to_max_polys(obj, height_ch.subdiv_on_max_polys * 1000 * proportions[obj.name], subsurf)

        #elif subsurf:
        #    subsurf.render_levels = obj.yp.ori_subsurf_render_levels
        #    subsurf.levels = obj.yp.ori_subsurf_levels

        # Set subsurf to visible
        if subsurf:
            subsurf.show_render = True
            subsurf.show_viewport = True

        # Displace Modifier
        displace = get_displace_modifier(obj)
        if yp.use_baked and height_ch.enable_subdiv_setup and not height_ch.subdiv_adaptive:

            mod_len = len(obj.modifiers)

            if not displace:
                displace = obj.modifiers.new('yP_Displace', 'DISPLACE')

            # Check modifier index
            for i, m in enumerate(obj.modifiers):
                if m == subsurf:
                    subsurf_idx = i
                elif m == displace:
                    displace_idx = i

            # Move up if displace is not directly below subsurf
            #if displace_idx != subsurf_idx+1:
            delta = displace_idx - subsurf_idx
            #print(obj, delta, subsurf.name)
            if delta > 1:
                for i in range(delta-1):
                    bpy.ops.object.modifier_move_up(modifier=displace.name)
            elif delta < 0:
                for i in range(abs(delta)):
                    bpy.ops.object.modifier_move_up(modifier=subsurf.name)

            #tex = displace.texture
            tex = [t for t in bpy.data.textures if hasattr(t, 'image') and t.image == img]
            if tex: 
                tex = tex[0]
            else:
                tex = bpy.data.textures.new(img.name, 'IMAGE')
                tex.image = img
            
            displace.texture = tex
            displace.texture_coords = 'UV'

            displace.strength = height_ch.subdiv_tweak * max_height
            displace.mid_level = height_ch.parallax_ref_plane
            displace.uv_layer = yp.baked_uv_name

            # Set displace to visible
            displace.show_render = True
            displace.show_viewport = True

        else:

            for mod in obj.modifiers:
                if mod.type == 'DISPLACE' and mod.name == 'yP_Displace':
                    if mod.texture:
                        bpy.data.textures.remove(mod.texture)
                    obj.modifiers.remove(mod)

        # Adaptive subdiv
        if yp.use_baked and height_ch.enable_subdiv_setup and height_ch.subdiv_adaptive:
            if not subsurf:
                subsurf = obj.modifiers.new('Subsurf', 'SUBSURF')
                if obj.type == 'MESH' and is_mesh_flat_shaded(obj.data):
                    subsurf.subdivision_type = 'SIMPLE'
            obj.cycles.use_adaptive_subdivision = True

        else:
            obj.cycles.use_adaptive_subdivision = False

    set_active_object(ori_active_obj)

def update_subdiv_setup(self, context):
    height_ch = self
    obj = context.object
    tree = self.id_data
    yp = tree.yp

    # Check uv nodes to enable/disable parallax
    check_uv_nodes(yp)

    # Check subdiv setup
    check_subdiv_setup(self)

    # Recover original subsurf levels if subdiv adaptive is active
    if yp.use_baked and height_ch.enable_subdiv_setup and height_ch.subdiv_adaptive:
        recover_subsurf_levels()

    # Reconnect nodes
    rearrange_yp_nodes(tree)
    reconnect_yp_nodes(tree)

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
    mat = get_active_material()
    objs = get_all_objects_with_same_materials(mat, True)

    if height_ch.enable_subdiv_setup and yp.use_baked:
        remember_subsurf_levels()

    update_subdiv_setup(self, context)

    if not height_ch.enable_subdiv_setup and yp.use_baked:
        recover_subsurf_levels()

def update_subdiv_tweak(self, context):
    mat = get_active_material()
    tree = self.id_data
    yp = tree.yp
    height_ch = self
    objs = get_all_objects_with_same_materials(mat, True)

    end_max_height = tree.nodes.get(height_ch.end_max_height)
    end_max_height_tweak = tree.nodes.get(height_ch.end_max_height_tweak)
    if end_max_height_tweak:
        end_max_height_tweak.inputs[1].default_value = height_ch.subdiv_tweak

    for obj in objs:
        displace = get_displace_modifier(obj)
        if displace and end_max_height:
            displace.strength = height_ch.subdiv_tweak * end_max_height.outputs[0].default_value

    if yp.enable_baked_outside:
        frame = get_node(mat.node_tree, yp.baked_outside_frame)
        disp = get_node(mat.node_tree, height_ch.baked_outside_disp_process, parent=frame)
        if disp:
            if is_greater_than_280():
                disp.inputs['Scale'].default_value = get_displacement_max_height(height_ch) * height_ch.subdiv_tweak
            else: disp.inputs[1].default_value = get_displacement_max_height(height_ch) * height_ch.subdiv_tweak

def setup_subdiv_to_max_polys(obj, max_polys, subsurf=None):
    
    if obj.type != 'MESH': return
    if not subsurf: subsurf = get_subsurf_modifier(obj)
    if not subsurf: return

    # Check object polygons
    num_poly = len(obj.data.polygons)

    # Get levels
    level = int(math.log(max_polys / num_poly, 4))

    if subsurf.type == 'MULTIRES':
        if level > subsurf.total_levels: level = subsurf.total_levels
    else:
        # Maximum subdivision is 10
        if level > 10: level = 10

    subsurf.render_levels = level
    subsurf.levels = level

def get_objs_size_proportions(objs):

    sizes = []
    
    for obj in objs:
        sorted_dim = sorted(obj.dimensions, reverse=True)
        # Object size is only measured on its largest 2 dimensions because this should works on a plane too
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
    height_ch = self
    objs = get_all_objects_with_same_materials(mat, True)

    if not yp.use_baked or not height_ch.enable_subdiv_setup or self.subdiv_adaptive: return

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
