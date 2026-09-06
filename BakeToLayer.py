import bpy, re, time, math, bmesh
from bpy.props import *
from mathutils import *
from .common import *
from .bake_common import *
from .subtree import *
from .input_outputs import *
from .node_connections import *
from .node_arrangements import *
from . import lib, layer_common, mask_common, ImageAtlas, UDIM, vector_displacement_lib, vector_displacement, BaseOperator

class YTryToSelectBakedVertexSelect(bpy.types.Operator):
    bl_idname = "wm.y_try_to_select_baked_vertex"
    bl_label = "Try to reselect baked selected vertex"
    bl_description = "Try to reselect baked selected vertex. It might give you wrong results if mesh number of vertex changed"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return get_active_ypaint_node() and context.object.type == 'MESH'

    def execute(self, context):
        if not hasattr(context, 'bake_info'):
            return {'CANCELLED'}

        bi = context.bake_info

        if len(bi.selected_objects) == 0:
            return {'CANCELLED'}

        if context.object.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.select_all(action='DESELECT')

        scene_objs = get_scene_objects()
        objs = []
        for bso in bi.selected_objects:
            if is_bl_newer_than(2, 79):
                bsoo = bso.object
            else: bsoo = scene_objs.get(bso.object_name)

            if bsoo and bsoo not in objs:
                objs.append(bsoo)

        # Get actual selectable objects
        actual_selectable_objs = []
        for o in objs:
            if is_bl_newer_than(2, 80):
                layer_cols = get_object_parent_layer_collections([], bpy.context.view_layer.layer_collection, o)

                #for lc in layer_cols:
                #    print(lc.name)
                
                if layer_cols and not any([lc for lc in layer_cols if lc.exclude or lc.hide_viewport or lc.collection.hide_viewport]):
                    actual_selectable_objs.append(o)
            else:
                if not o.hide_select and in_active_279_layer(o):
                    actual_selectable_objs.append(o)

        if len(actual_selectable_objs) == 0:
            self.report({'ERROR'}, "Cannot select the object!")
            return {'CANCELLED'}

        for i, obj in enumerate(actual_selectable_objs):
            set_object_hide(obj, False)
            set_object_select(obj, True)
            if i == 0: set_active_object(obj)
        
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.reveal()
        bpy.ops.mesh.select_all(action='DESELECT')

        for bso in bi.selected_objects:
            if is_bl_newer_than(2, 79):
                obj = bso.object
            else: obj = scene_objs.get(bso.object_name)

            if not obj or obj not in actual_selectable_objs: continue

            mesh = obj.data
            bm = bmesh.from_edit_mesh(mesh)

            bm.verts.ensure_lookup_table()
            bm.edges.ensure_lookup_table()
            bm.faces.ensure_lookup_table()

            if bi.selected_face_mode:
                context.tool_settings.mesh_select_mode[0] = False
                context.tool_settings.mesh_select_mode[1] = False
                context.tool_settings.mesh_select_mode[2] = True

                for bsv in bso.selected_vertex_indices:
                    try: bm.faces[bsv.index].select = True
                    except: pass
            else:
                context.tool_settings.mesh_select_mode[0] = True
                context.tool_settings.mesh_select_mode[1] = False
                context.tool_settings.mesh_select_mode[2] = False

                for bsv in bso.selected_vertex_indices:
                    try: bm.verts[bsv.index].select = True
                    except: pass

        return {'FINISHED'}

class YRemoveBakeInfoOtherObject(bpy.types.Operator):
    bl_idname = "wm.y_remove_bake_info_other_object"
    bl_label = "Remove other object info"
    bl_description = "Remove other object bake info, so it won't be automatically baked anymore if you choose to rebake"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return get_active_ypaint_node() and context.object.type == 'MESH'

    def execute(self, context):
        if not hasattr(context, 'other_object') or not hasattr(context, 'bake_info'):
            return {'CANCELLED'}

        #if len(context.bake_info.other_objects) == 1:
        #    self.report({'ERROR'}, "Cannot delete, need at least one object!")
        #    return {'CANCELLED'}

        for i, oo in enumerate(context.bake_info.other_objects):
            if oo == context.other_object:
                context.bake_info.other_objects.remove(i)
                break

        return {'FINISHED'}

class YBakeToLayer(bpy.types.Operator, BaseBakeOperator):
    bl_idname = "wm.y_bake_to_layer"
    bl_label = "Bake To Layer"
    bl_description = "Bake something as layer/mask"
    bl_options = {'REGISTER', 'UNDO'}

    name = StringProperty(
        name = 'Image Name',
        description = 'Baked image name',
        default = ''
    )

    uv_map = StringProperty(
        name = 'UV Map', 
        description = 'UV Map to use for baked image coordinate', 
        default = '',
        update = BaseOperator.update_uv_map_name
    )

    uv_map_coll = CollectionProperty(type=BaseOperator.YPropertyGroup)

    uv_map_1 = StringProperty(default='')

    interpolation = EnumProperty(
        name = 'Image Interpolation Type',
        description = 'Image interpolation type',
        items = interpolation_type_items,
        default = 'Linear'
    )

    # For choosing overwrite entity from list
    overwrite_choice = BoolProperty(
        name = 'Overwrite existing layer',
        description = 'Overwrite existing layer',
        default = False
    )

    # For rebake button
    overwrite_current = BoolProperty(default=False)

    overwrite_name = StringProperty(
        name = 'Overwritten Image Name',
        description = 'Image name that will be overwritten',
        default = ''
    )
    overwrite_coll = CollectionProperty(type=BaseOperator.YPropertyGroup)

    overwrite_image_name = StringProperty(default='')
    overwrite_segment_name = StringProperty(default='')

    type = EnumProperty(
        name = 'Bake Type',
        description = 'Bake Type',
        items = bake_type_items,
        default = 'AO'
    )

    # Other objects props

    use_cage = BoolProperty(
        name = 'Cage Object',
        description = 'Cast rays to active material objects from a cage',
        default = False
    )

    cage_object_name = StringProperty(
        name = 'Cage Object',
        description = 'Object to use as cage instead of calculating the cage from the active object with cage extrusion',
        default = ''
    )

    cage_object_coll = CollectionProperty(type=BaseOperator.YPropertyGroup)

    cage_extrusion = FloatProperty(
        name = 'Cage Extrusion',
        description = 'Inflate the active object by the specified distance for baking. This helps matching to points nearer to the outside of the selected object meshes',
        default=0.2, min=0.0, max=1.0
    )

    max_ray_distance = FloatProperty(
        name = 'Max Ray Distance',
        description = 'The maximum ray distance for matching points between the active and selected objects. If zero, there is no limit',
        default=0.2, min=0.0, max=1.0
    )

    use_transparent_for_missing_rays = BoolProperty(
        name = 'Use Transparent for Missing Rays',
        description = 'Use transparent for missing rays',
        default = True
    )

    normalize = BoolProperty(
        name = 'Normalize Bake Result',
        description = 'Normalize the bake result',
        default = True,
    )
    
    # AO Props
    ao_distance = FloatProperty(
        name = 'AO Distance',
        description = 'Ambient occlusion distance',
        default = 1.0
    )

    # Bevel Props
    bevel_samples = IntProperty(
        name = 'Bevel Samples',
        description = 'Bevel samples',
        default=4, min=2, max=16
    )

    bevel_radius = FloatProperty(
        name = 'Bevel Radius',
        description = 'Bevel distance radius',
        default=0.05, min=0.0, max=1000.0
    )

    edge_detect_method = EnumProperty(
        name = 'Edge Detection Method',
        description = 'Edge detection method',
        items = (
            ('DOT', 'Dot Product', ''),
            ('CROSS', 'Cross Product', '')
        ),
        default='DOT'
    )

    # Wireframe Props
    wireframe_size = FloatProperty(
        name = 'Wireframe Size',
        description = 'Wireframe thickness in Blender units',
        default=0.001, min=0.0, max=100.0, precision=4
    )

    wireframe_triangulated = BoolProperty(
        name = 'Triangulated',
        description = 'Use the triangulated wireframe rather than the actual polygons',
        default = False
    )

    # Curvature Props
    curvature_distance = FloatProperty(
        name = 'Curvature Distance',
        description = 'Curvature sampling distance',
        default=0.05, min=0.0, max=1000.0
    )

    multires_base = IntProperty(
        name = 'Multires Base',
        description = 'Baking will use the difference between the base level and max level,\nand after baking, base level will be used in the multires modifier',
        default=1, min=0, max=16
    )

    target_type = EnumProperty(
        name = 'Target Bake Type',
        description = 'Target Bake Type',
        items = (
            ('LAYER', 'Layer', ''),
            ('MASK', 'Mask', '')
        ),
        default='LAYER'
    )

    fxaa = BoolProperty(
        name = 'Use FXAA', 
        description = "Use FXAA on baked image (doesn't work with float images)",
        default = True
    )

    ssaa = BoolProperty(
        name = 'Use SSAA', 
        description = "Use Supersample AA on baked image",
        default = False
    )

    denoise = BoolProperty(
        name = 'Use Denoise', 
        description = "Use Denoise on baked image",
        default = True
    )

    channel_idx = EnumProperty(
        name = 'Channel',
        description = 'Channel of new layer, can be changed later',
        items = BaseOperator.channel_items
    )

    blend_type = EnumProperty(
        name = 'Blend',
        items = blend_type_items,
    )

    height_blend_type = EnumProperty(
        name = 'Height Blend Type',
        description = 'Height blend type',
        items = height_blend_type_items,
        default = 'MIX'
    )

    normal_blend_type = EnumProperty(
        name = 'Normal Blend Type',
        description = 'Normal blend type',
        items = normal_blend_type_items,
        default = 'MIX'
    )

    normal_map_type = EnumProperty(
        name = 'Normal Map Type',
        description = 'Normal map type of this layer',
        items = layer_common.get_normal_map_type_items
    )

    hdr = BoolProperty(
        name = '32-bit Float',
        description = 'Use 32-bit float image',
        default = True
    )

    use_baked_disp = BoolProperty(
        name = 'Use Displacement Setup',
        description = 'Use displacement setup, this will also apply subdiv setup on object',
        default = False
    )

    flip_normals = BoolProperty(
        name = 'Flip Normals',
        description = 'Flip normal of mesh',
        default = False
    )

    only_local = BoolProperty(
        name = 'Only Local',
        description = 'Only bake local ambient occlusion',
        default = False
    )

    subsurf_influence = BoolProperty(
        name = 'Subsurf / Multires Influence',
        description = 'Take account subsurf or multires when baking cavity',
        default = True
    )

    force_bake_all_polygons = BoolProperty(
        name = 'Force Bake all Polygons',
        description = 'Force bake all polygons, useful if material is not using direct polygon (ex: solidify material)',
        default = False
    )

    use_image_atlas = BoolProperty(
        name = 'Use Image Atlas',
        description = 'Use Image Atlas',
        default = False
    )

    use_udim = BoolProperty(
        name = 'Use UDIM Tiles',
        description = 'Use UDIM Tiles',
        default = False
    )
    
    hide_source_objects = BoolProperty(
        name = 'Hide Source Objects after Baking',
        description = 'Hide source objects after baking',
        default = True
    )

    @classmethod
    def poll(cls, context):
        return get_active_ypaint_node() and context.object.type == 'MESH'

    @classmethod
    def description(self, context, properties):
        return get_operator_description(self)

    def invoke(self, context, event):
        self.invoke_operator(context)

        if hasattr(context, 'entity'):
            self.entity = context.entity
        else: self.entity = None

        obj = self.obj = context.object
        scene = self.scene = context.scene
        node = get_active_ypaint_node()
        yp = node.node_tree.yp
        ypup = get_user_preferences()

        # UDIM is turned off by default
        #self.use_udim = False

        # Default normal map type is bump
        self.normal_map_type = 'BUMP_MAP'

        # Default FXAA is on
        #self.fxaa = True

        # Default samples is 1
        self.samples = 1

        # Set channel to first one, just in case
        if len(yp.channels) > 0:
            self.channel_idx = str(0)

        # Get height channel
        height_root_ch = get_root_height_channel(yp)
        normal_root_ch = get_root_normal_channel(yp)

        # Set default float image
        # Curvature uses float so it stays a data map with 0.5 as the flat value
        if self.type in {'POINTINESS', 'MULTIRES_DISPLACEMENT', 'CURVATURE'}:
            self.hdr = True
        else:
            self.hdr = False

        # Set name
        mat = get_active_material()
        if self.type == 'AO':
            self.blend_type = 'MULTIPLY'
            self.samples = 32

            # Check Ambient occlusion channel if available
            for i, c in enumerate(yp.channels):
                if c.name in {'Ambient Occlusion', 'AO'}:
                    self.channel_idx = str(i)
                    break

        elif self.type == 'POINTINESS':
            self.blend_type = 'ADD'
            self.fxaa = False
        elif self.type == 'CAVITY':
            self.blend_type = 'ADD'
        elif self.type == 'DUST':
            self.blend_type = 'MIX'
        elif self.type == 'PAINT_BASE':
            self.blend_type = 'MIX'
        elif self.type == 'THICKNESS':
            self.blend_type = 'MIX'
            self.samples = 32
            self.only_local = True
        elif self.type == 'WIREFRAME':
            self.blend_type = 'MIX'
            self.ssaa = True
        elif self.type == 'CURVATURE':
            self.blend_type = 'MIX'
            self.samples = 8
        elif self.type == 'BEVEL_NORMAL':
            self.blend_type = 'MIX'
            self.normal_blend_type = 'OVERLAY'
            self.use_baked_disp = False
            self.samples = 32

            if normal_root_ch:
                self.channel_idx = str(get_channel_index(normal_root_ch))
                #self.normal_map_type = 'NORMAL_MAP'

        elif self.type == 'BEVEL_MASK':
            self.blend_type = 'MIX'
            self.use_baked_disp = False
            self.samples = 32

        elif self.type == 'MULTIRES_NORMAL':
            self.blend_type = 'MIX'

            if normal_root_ch:
                self.channel_idx = str(get_channel_index(normal_root_ch))
                #self.normal_map_type = 'NORMAL_MAP'
                self.normal_blend_type = 'OVERLAY'

        elif self.type == 'MULTIRES_DISPLACEMENT':
            self.blend_type = 'MIX'

            if height_root_ch:
                self.channel_idx = str(get_channel_index(height_root_ch))
                #self.normal_map_type = 'BUMP_MAP'
                self.normal_blend_type = 'OVERLAY'

        elif self.type == 'OTHER_OBJECT_EMISSION':
            self.blend_type = 'MIX'
            self.subsurf_influence = False

            self.margin = 0

        elif self.type in {'OTHER_OBJECT_NORMAL', 'OBJECT_SPACE_NORMAL'}:
            self.subsurf_influence = False

            if normal_root_ch:
                self.channel_idx = str(get_channel_index(normal_root_ch))
                #self.normal_map_type = 'NORMAL_MAP'
                self.normal_blend_type = 'OVERLAY'

            if self.type == 'OTHER_OBJECT_NORMAL':
                self.margin = 0

        elif self.type == 'OTHER_OBJECT_CHANNELS':
            self.blend_type = 'MIX'
            self.subsurf_influence = False
            self.use_image_atlas = False
            self.margin = 0

        elif self.type == 'SELECTED_VERTICES':
            self.subsurf_influence = False
            self.use_baked_disp = False

        elif self.type == 'FLOW':
            self.blend_type = 'MIX'

            # Check flow channel if available
            for i, c in enumerate(yp.channels):
                if 'flow' in c.name.lower():
                    self.channel_idx = str(i)
                    break

        suffix = bake_type_suffixes[self.type]
        self.name = get_unique_name(mat.name + ' ' + suffix, bpy.data.images)

        self.overwrite_choice = False
        self.overwrite_name = ''
        overwrite_entity = None
        
        if self.overwrite_current:
            overwrite_entity = self.entity

        # Other object and selected vertices bake will not display overwrite choice
        elif not self.type.startswith('OTHER_OBJECT_') and self.type not in {'SELECTED_VERTICES'}:
        #else:

            # Clear overwrite_coll
            self.overwrite_coll.clear()

            # Get overwritable layers
            if self.target_type == 'LAYER':
                for layer in yp.layers:
                    if layer.type == 'IMAGE':
                        source = get_layer_source(layer)
                        if source.image:
                            img = source.image
                            if img.y_bake_info.is_baked and not img.y_bake_info.is_baked_channel and img.y_bake_info.bake_type == self.type:
                                self.overwrite_coll.add().name = layer.name
                            elif img.yia.is_image_atlas or img.yua.is_udim_atlas:
                                if img.yia.is_image_atlas:
                                    segment = img.yia.segments.get(layer.segment_name)
                                else: segment = img.yua.segments.get(layer.segment_name)
                                if segment and segment.bake_info.is_baked and segment.bake_info.bake_type == self.type:
                                    self.overwrite_coll.add().name = layer.name

            # Get overwritable masks
            elif len(yp.layers) > 0:
                active_layer = yp.layers[yp.active_layer_index]
                for mask in active_layer.masks:
                    if mask.type == 'IMAGE':
                        source = get_mask_source(mask)
                        if source.image:
                            img = source.image
                            if img.y_bake_info.is_baked and not img.y_bake_info.is_baked_channel and img.y_bake_info.bake_type == self.type:
                                self.overwrite_coll.add().name = mask.name
                            elif img.yia.is_image_atlas or img.yua.is_udim_atlas:
                                if img.yia.is_image_atlas:
                                    segment = img.yia.segments.get(mask.segment_name)
                                else: segment = img.yua.segments.get(mask.segment_name)
                                if segment and segment.bake_info.is_baked and segment.bake_info.bake_type == self.type:
                                    self.overwrite_coll.add().name = mask.name

            if len(self.overwrite_coll) > 0:

                self.overwrite_choice = True
                if self.target_type == 'LAYER':
                    overwrite_entity = yp.layers.get(self.overwrite_coll[0].name)
                else: 
                    active_layer = yp.layers[yp.active_layer_index]
                    overwrite_entity = active_layer.masks.get(self.overwrite_coll[0].name)
            else:
                self.overwrite_choice = False

        self.overwrite_image_name = ''
        self.overwrite_segment_name = ''
        if overwrite_entity:

            if self.target_type == 'LAYER':
                source = get_layer_source(overwrite_entity)
            else: source = get_mask_source(overwrite_entity)

            bi = None
            if overwrite_entity.type == 'IMAGE' and source.image:
                self.overwrite_image_name = source.image.name
                if not source.image.yia.is_image_atlas and not source.image.yua.is_udim_atlas:
                    self.overwrite_name = source.image.name
                    self.width = source.image.size[0] if source.image.size[0] != 0 else int(ypup.default_image_resolution)
                    self.height = source.image.size[1] if source.image.size[1] != 0 else int(ypup.default_image_resolution)
                    self.use_image_atlas = False
                    bi = source.image.y_bake_info
                else:
                    self.overwrite_name = overwrite_entity.name
                    self.overwrite_segment_name = overwrite_entity.segment_name
                    if source.image.yia.is_image_atlas:
                        segment = source.image.yia.segments.get(overwrite_entity.segment_name)
                        self.width = segment.width
                        self.height = segment.height
                    else: 
                        segment = source.image.yua.segments.get(overwrite_entity.segment_name)
                        tilenums = UDIM.get_udim_segment_tilenums(segment)
                        if len(tilenums) > 0:
                            tile = source.image.tiles.get(tilenums[0])
                            self.width = tile.size[0]
                            self.height = tile.size[1]
                    bi = segment.bake_info
                    self.use_image_atlas = True
                self.hdr = source.image.is_float

            # Fill settings using bake info stored on image
            if bi:
                for attr in dir(bi):
                    if attr in {'other_objects', 'selected_objects'}: continue
                    if attr.startswith('__'): continue
                    if attr.startswith('bl_'): continue
                    if attr in {'rna_type'}: continue
                    #if attr in dir(self):
                    try: setattr(self, attr, getattr(bi, attr))
                    except: pass

            self.uv_map = overwrite_entity.uv_name
        
        # Use active uv layer name by default
        uv_layers = get_uv_layers(obj)

        # UV Map collections update
        self.uv_map_coll.clear()
        for uv in uv_layers:
            if not uv.name.startswith(TEMP_UV):
                self.uv_map_coll.add().name = uv.name

        if len(self.uv_map_coll) > 0 and not overwrite_entity: #len(self.overwrite_coll) == 0:
            self.uv_map = self.uv_map_coll[0].name

        if len(self.uv_map_coll) > 1:
            self.uv_map_1 = self.uv_map_coll[1].name

        # Cage object collections update
        self.cage_object_coll.clear()
        for ob in get_scene_objects():
            if ob != obj and ob not in bpy.context.selected_objects and ob.type == 'MESH':
                self.cage_object_coll.add().name = ob.name
 
        requires_popup = self.type in {'OTHER_OBJECT_NORMAL', 'OTHER_OBJECT_EMISSION', 'OTHER_OBJECT_CHANNELS', 'FLOW'}
        if not requires_popup and get_user_preferences().skip_property_popups and not event.shift:
            return self.execute(context)

        width = 320
        if self.type.startswith('OTHER_OBJECT_'):
            width = 350

        return context.window_manager.invoke_props_dialog(self, width=width)

    def check(self, context):
        self.check_operator(context)
        ypup = get_user_preferences()

        # New image cannot use more pixels than the image atlas
        if self.use_image_atlas:
            if self.hdr: max_size = ypup.hdr_image_atlas_size
            else: max_size = ypup.image_atlas_size
            if self.width > max_size: self.width = max_size
            if self.height > max_size: self.height = max_size

        return True

    def draw(self, context):
        node = get_active_ypaint_node()
        yp = node.node_tree.yp
        mat = get_active_material()

        channel = yp.channels[int(self.channel_idx)] if self.channel_idx != '-1' else None
        height_root_ch = get_root_height_channel(yp)

        show_subsurf_influence = not self.type.startswith('MULTIRES_') and (self.type not in {'SELECTED_VERTICES', 'WIREFRAME'} or (self.type == 'WIREFRAME' and is_bl_newer_than(2, 81) and not self.wireframe_triangulated))
        show_use_baked_disp = height_root_ch and not self.type.startswith('MULTIRES_') and self.type not in {'SELECTED_VERTICES'}

        split_val = 0.4

        lcol = self.layout.column(align=False)

        if not self.overwrite_current:

            if len(self.overwrite_coll) > 0:
                row = split_layout(lcol, split_val)
                right_aligned_label(row, 'Overwrite:')
                row.prop(self, 'overwrite_choice', text='')

            row = split_layout(lcol, split_val)
            if len(self.overwrite_coll) > 0 and self.overwrite_choice:
                if self.target_type == 'LAYER':
                    right_aligned_label(row, 'Overwrite Layer:')
                else: right_aligned_label(row, 'Overwrite Mask:')
                row.prop_search(self, "overwrite_name", self, "overwrite_coll", text='', icon='IMAGE_DATA')
            else:
                right_aligned_label(row, 'Name:')
                row.prop(self, 'name', text='')

                # Other object channels always bakes all channels
                if self.target_type == 'LAYER' and self.type != 'OTHER_OBJECT_CHANNELS':
                    row = split_layout(lcol, split_val)
                    right_aligned_label(row, 'Channel:')

                    rrow = row.row(align=True)
                    rrow.prop(self, 'channel_idx', text='')
                    if channel:
                        if channel.special_type == 'HEIGHT':
                            rrow.prop(self, 'height_blend_type', text='')
                        elif channel.special_type == 'NORMAL':
                            rrow.prop(self, 'normal_blend_type', text='')
                        else: 
                            rrow.prop(self, 'blend_type', text='')
        else:
            row = split_layout(lcol, split_val)
            right_aligned_label(row, 'Name:')
            row.label(text=self.overwrite_name)

        if self.type.startswith('OTHER_OBJECT_'):

            row = split_layout(lcol, split_val)
            row.label(text='')
            row.prop(self, 'use_cage')

            if self.use_cage:
                row = split_layout(lcol, split_val)
                right_aligned_label(row, 'Cage Object:')
                row.prop_search(self, "cage_object_name", self, "cage_object_coll", text='', icon='OBJECT_DATA')

            row = split_layout(lcol, split_val)

            rcol = row.column(align=True)
            if self.use_cage:
                right_aligned_label(rcol, 'Cage Extrusion:')
            else: right_aligned_label(rcol, 'Extrusion:')
            if hasattr(bpy.context.scene.render.bake, 'max_ray_distance'):
                right_aligned_label(rcol, 'Max Ray Distance:')

            rcol = row.column(align=True)
            rcol.prop(self, 'cage_extrusion', text='')
            if hasattr(bpy.context.scene.render.bake, 'max_ray_distance'):
                rcol.prop(self, 'max_ray_distance', text='')

            if self.type in {'OTHER_OBJECT_NORMAL'}:
                row = split_layout(lcol, split_val)
                row.label(text='')
                row.prop(self, 'use_transparent_for_missing_rays')

        elif self.type == 'POINTINESS' and is_bl_newer_than(2, 83):
            row = split_layout(lcol, split_val)
            row.label(text='')
            row.prop(self, 'normalize', text='Normalize Pointiness')

        elif self.type == 'AO':
            row = split_layout(lcol, split_val)
            right_aligned_label(row, 'AO Distance:')
            row.prop(self, 'ao_distance', text='')

            row = split_layout(lcol, split_val)
            row.label(text='')
            row.prop(self, 'only_local')

        elif self.type == 'THICKNESS':
            row = split_layout(lcol, split_val)
            right_aligned_label(row, 'Distance:')
            row.prop(self, 'ao_distance', text='')

            row = split_layout(lcol, split_val)
            row.label(text='')
            row.prop(self, 'only_local')

        elif self.type == 'WIREFRAME':
            row = split_layout(lcol, split_val)
            right_aligned_label(row, 'Wireframe Size:')
            row.prop(self, 'wireframe_size', text='')

            if is_bl_newer_than(2, 81):
                row = split_layout(lcol, split_val)
                row.label(text='')
                row.prop(self, 'wireframe_triangulated')

        elif self.type == 'CURVATURE':
            row = split_layout(lcol, split_val)
            right_aligned_label(row, 'Distance:')
            row.prop(self, 'curvature_distance', text='')

        elif self.type in {'BEVEL_NORMAL', 'BEVEL_MASK'}:
            row = split_layout(lcol, split_val)
            right_aligned_label(row, 'Bevel Samples:')
            row.prop(self, 'bevel_samples', text='')

            row = split_layout(lcol, split_val)
            right_aligned_label(row, 'Bevel Radius:')
            row.prop(self, 'bevel_radius', text='')

            if self.type == 'BEVEL_MASK':
                row = split_layout(lcol, split_val)
                right_aligned_label(row, 'Edge Detect Method:')

                crow = row.row(align=True)
                crow.prop(self, 'edge_detect_method', expand=True)

        elif self.type.startswith('MULTIRES_'):
            row = split_layout(lcol, split_val)
            right_aligned_label(row, 'Base Level:')
            row.prop(self, 'multires_base', text='')

        BaseOperator.draw_base_image_settings(self, lcol, split_val)

        row = split_layout(lcol, split_val)
        right_aligned_label(row, 'UV Map:')
        row.prop_search(self, "uv_map", self, "uv_map_coll", text='', icon='GROUP_UVS')

        if self.type == 'FLOW':
            row = split_layout(lcol, split_val)
            right_aligned_label(row, 'Straight UV Map:')
            row.prop_search(self, "uv_map_1", self, "uv_map_coll", text='', icon='GROUP_UVS')

        row = split_layout(lcol, split_val)
        right_aligned_label(row, 'Samples:')
        row.prop(self, 'samples', text='')

        row = split_layout(lcol, split_val)
        right_aligned_label(row, 'Margin:')
        if is_bl_newer_than(3, 1):
            split = split_layout(row, 0.4, align=True)
            split.prop(self, 'margin', text='')
            split.prop(self, 'margin_type', text='')
        else:
            row.prop(self, 'margin', text='')

        #row = split_layout(lcol, split_val)
        #right_aligned_label(row, text='Interpolation:')
        #row.prop(self, 'interpolation', text='')

        if self.target_type == 'MASK':
            row = split_layout(lcol, split_val)
            right_aligned_label(row, text='Blend:')
            row.prop(self, 'blend_type', text='')

        lcol.separator()

        row = split_layout(lcol, split_val)
        row.label(text='')
        if self.type.startswith('OTHER_OBJECT_'):
            row.prop(self, 'ssaa')
        else: row.prop(self, 'fxaa')

        if self.type == 'WIREFRAME':
            row = split_layout(lcol, split_val)
            row.label(text='')
            row.prop(self, 'ssaa')

        if self.type in {'AO', 'THICKNESS', 'BEVEL_MASK', 'BEVEL_NORMAL'} and is_bl_newer_than(2, 81):
            row = split_layout(lcol, split_val)
            row.label(text='')
            row.prop(self, 'denoise')

        lcol.separator()

        if show_subsurf_influence:
            row = split_layout(lcol, split_val)
            row.label(text='')

            r = row.row()
            r.active = not self.use_baked_disp
            r.prop(self, 'subsurf_influence')

        #if height_root_ch and not self.type.startswith('MULTIRES_'):
        if show_use_baked_disp:
            row = split_layout(lcol, split_val)
            row.label(text='')
            row.prop(self, 'use_baked_disp')

        row = split_layout(lcol, split_val)
        row.label(text='')
        row.prop(self, 'flip_normals')

        row = split_layout(lcol, split_val)
        row.label(text='')
        row.prop(self, 'force_bake_all_polygons')

        sep_added = False

        if self.type not in {'OTHER_OBJECT_CHANNELS'}:
            lcol.separator()
            sep_added = True

            row = split_layout(lcol, split_val)
            row.label(text='')

            r = row.row()
            #r.active = not self.use_udim
            r.prop(self, 'use_image_atlas')

        if UDIM.is_udim_supported():
            if not sep_added:
                lcol.separator()
                sep_added = True

            row = split_layout(lcol, split_val)
            row.label(text='')
            r = row.row()
            r.prop(self, 'use_udim')

        if is_bl_newer_than(2, 79) and self.type.startswith('OTHER_OBJECT_'):
            if not sep_added:
                lcol.separator()
                sep_added = True

            row = split_layout(lcol, split_val)
            row.label(text='')
            r = row.row()
            r.prop(self, 'hide_source_objects')

        if is_bl_newer_than(2, 80):
            lcol.separator()

            row = split_layout(lcol, split_val)
            right_aligned_label(row, 'Bake Device:')
            row.prop(self, 'bake_device', text='')

    def execute(self, context):
        if not self.execute_operator_prep(context): return {'CANCELLED'}

        node = get_active_ypaint_node()
        yp = node.node_tree.yp

        if (self.overwrite_choice or self.overwrite_current) and self.overwrite_name == '':
            self.report({'ERROR'}, "Overwrite layer/mask cannot be empty!")
            return self.execute_operator_cancelled(context)

        # Get overwrite image
        overwrite_img = None
        segment = None
        if (self.overwrite_choice or self.overwrite_current) and self.overwrite_image_name != '':
            overwrite_img = bpy.data.images.get(self.overwrite_image_name)

            if overwrite_img.yia.is_image_atlas:
                segment = overwrite_img.yia.segments.get(self.overwrite_segment_name)
            elif overwrite_img.yua.is_udim_atlas:
                segment = overwrite_img.yua.segments.get(self.overwrite_segment_name)

        # Get bake properties
        bprops = get_bake_properties_from_self(self)

        rdict = bake_to_entity(bprops, overwrite_img, segment)

        if rdict['message'] != '':
            self.report({'ERROR'}, rdict['message'])
            return self.execute_operator_cancelled(context)

        active_id = rdict['active_id']
        image = rdict['image']

        # Refresh active index (only when not overwriting current entity)
        #if active_id != yp.active_layer_index:
        if active_id != None and not self.overwrite_current:
            yp.active_layer_index = active_id
        elif image:
            update_image_editor_image(context, image)

        # Expand image source to show rebake button
        ypui = context.window_manager.ypui
        if self.target_type == 'MASK':
            ypui.layer_ui.expand_masks = True
        else:
            ypui.layer_ui.expand_content = True
            ypui.layer_ui.expand_source = True
        ypui.need_update = True

        if image: 
            self.report({'INFO'}, 'Baking '+bake_type_labels[self.type]+' is done in '+'{:0.2f}'.format(rdict['time_elapsed'])+' seconds!')

        return self.execute_operator_finished(context)

class YBakeEntityToImage(bpy.types.Operator, BaseBakeOperator):
    bl_idname = "wm.y_bake_entity_to_image"
    bl_label = "Bake Layer/Mask To Image"
    bl_description = "Bake Layer/Mask to an image"
    bl_options = {'UNDO'}

    name = StringProperty(
        name = 'Image Name',
        description = 'Baked Image Name',
        default = ''
    )

    uv_map = StringProperty(
        name = 'UV Map', 
        description = 'UV Map to use for baked image coordinate', 
        default = '',
        update = BaseOperator.update_uv_map_name
    )

    uv_map_coll = CollectionProperty(type=BaseOperator.YPropertyGroup)

    hdr = BoolProperty(
        name = '32-bit Float',
        description = 'Use 32-bit float image',
        default = False
    )

    fxaa = BoolProperty(
        name = 'Use FXAA', 
        description = "Use FXAA to baked image (doesn't work with float images)",
        default = True
    )

    denoise = BoolProperty(
        name = 'Use Denoise', 
        description = 'Use Denoise on baked images',
        default = False
    )

    use_image_atlas = BoolProperty(
        name = 'Use Image Atlas',
        description = 'Use Image Atlas',
        default = False
    )
    
    blur_type = EnumProperty(
        name = 'Blur Type', 
        description = 'Blur type for the baked image',
        items = (
            ('NOISE', 'Noise', 'Noisy and need more samples but has matching value to the blur vector option'),
            ('FLAT', 'Flat', 'Flat blur'),
            ('TENT', 'Tent', 'Tent blur'),
            ('QUAD', 'Quadratic', 'Quadratic blur'),
            ('CUBIC', 'Cubic', 'Cubic blur'),
            ('GAUSS', 'Gaussian', 'Gausssian blur'),
            ('FAST_GAUSS', 'Fast Gaussian', 'Fast gausssian blur'),
            ('CATROM', 'Catrom', 'Catrom blur'),
            ('MITCH', 'Mitch', 'Mitch blur')
        ),
        default='GAUSS'
    )

    blur = BoolProperty(
        name = 'Use Blur', 
        description = 'Use blur to the baked image',
        default = False
    )

    blur_factor = FloatProperty(
        name = 'Blur Factor',
        description = 'Blur factor to the baked image',
        default=1.0, min=0.0, max=100.0
    )

    blur_size = FloatProperty(
        name = 'Blur Size',
        description = 'Blur size (in pixels) to the baked image',
        default=10.0, min=0.0
    )

    duplicate_entity = BoolProperty(
        name = 'Duplicate Entity',
        description = 'Duplicate entity',
        default = False
    )

    disable_current = BoolProperty(
        name = 'Disable current layer/mask',
        description = 'Disable current layer/mask',
        default = True
    )

    use_udim = BoolProperty(
        name = 'Use UDIM Tiles',
        description = 'Use UDIM Tiles',
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

        obj = context.object
        ypup = get_user_preferences()
        node = get_active_ypaint_node()
        yp = node.node_tree.yp

        self.entity = context.entity
        self.layer = None
        self.mask = None

        if not hasattr(context, 'entity'):
            return self.execute(context)

        # Check entity
        m1 = re.match(r'^yp\.layers\[(\d+)\]$', self.entity.path_from_id())
        m2 = re.match(r'^yp\.layers\[(\d+)\]\.masks\[(\d+)\]$', self.entity.path_from_id())

        if m1: 
            self.layer = yp.layers[int(m1.group(1))]
            self.mask = None
            self.index = int(m1.group(1))
            self.entities = yp.layers

            # NOTE: Duplicate entity currently doesn't work on layer so make sure to disable it
            self.duplicate_entity = False
        elif m2: 
            self.layer = yp.layers[int(m2.group(1))]
            self.mask = self.layer.masks[int(m2.group(2))]
            self.index = int(m2.group(2))
            self.entities = self.layer.masks
        else: 
            return self.execute(context)

        if self.mask: source_tree = get_mask_tree(self.mask)
        else: source_tree = get_source_tree(self.layer)
        baked_source = source_tree.nodes.get(self.entity.baked_source)

        overwrite_image = None
        if baked_source and baked_source.image:
            overwrite_image = baked_source.image

        if overwrite_image and not overwrite_image.yia.is_image_atlas and not overwrite_image.yua.is_udim_atlas:
            self.name = overwrite_image.name
        else:
            name = node.node_tree.name.replace(get_addon_title()+' ', '')
            self.name = name + ' ' + self.entity.name
            #if not self.name.endswith(' Image'):
            #    self.name += ' Image'

            self.name = get_unique_name(self.name, bpy.data.images)

        # Use active uv layer name by default
        uv_layers = get_uv_layers(obj)

        # UV Map collections update
        self.uv_map_coll.clear()
        for uv in uv_layers:
            if not uv.name.startswith(TEMP_UV):
                self.uv_map_coll.add().name = uv.name

        if overwrite_image:

            # Get segment set width and height
            segment = None
            if overwrite_image.yia.is_image_atlas:
                segment = overwrite_image.yia.segments.get(self.entity.baked_segment_name)
                self.width = segment.width
                self.height = segment.height
            elif overwrite_image.yua.is_udim_atlas:
                segment = overwrite_image.yua.segments.get(self.entity.baked_segment_name)
                tilenums = UDIM.get_udim_segment_tilenums(segment)
                if len(tilenums) > 0:
                    tile = overwrite_image.tiles.get(tilenums[0])
                    self.width = tile.size[0]
                    self.height = tile.size[1]
            else:
                self.width = overwrite_image.size[0] if overwrite_image.size[0] != 0 else ypup.default_new_image_size
                self.height = overwrite_image.size[1] if overwrite_image.size[1] != 0 else ypup.default_new_image_size

            # Get bake info
            bi = segment.bake_info if segment else overwrite_image.y_bake_info

            for attr in dir(bi):
                if attr in {'other_objects', 'selected_objects'}: continue
                if attr.startswith('__'): continue
                if attr.startswith('bl_'): continue
                if attr in {'rna_type'}: continue
                #if attr in dir(self):
                try: setattr(self, attr, getattr(bi, attr))
                except: pass

            if self.entity.baked_uv_name != '' and self.entity.baked_uv_name in self.uv_map_coll:
                self.uv_map = self.entity.baked_uv_name
            elif self.entity.uv_name in self.uv_map_coll:
                self.uv_map = self.entity.uv_name

        else:
            if len(self.uv_map_coll) > 0:
                self.uv_map = self.uv_map_coll[0].name

            if self.entity.type in {'EDGE_DETECT', 'HEMI', 'AO'}:
                #self.hdr = True
                self.fxaa = False
            else: 
                #self.hdr = False
                self.fxaa = True

            # Auto set some props for some types
            if self.entity.type in {'EDGE_DETECT', 'AO'}:
                self.samples = 32
                self.denoise = True
            else:
                self.samples = 1
                self.denoise = False

        if get_user_preferences().skip_property_popups and not event.shift:
            return self.execute(context)

        return context.window_manager.invoke_props_dialog(self, width=320)

    def check(self, context):
        self.check_operator(context)
        ypup = get_user_preferences()

        # New image cannot use more pixels than the image atlas
        if self.use_image_atlas:
            if self.hdr: max_size = ypup.hdr_image_atlas_size
            else: max_size = ypup.image_atlas_size
            if self.width > max_size: self.width = max_size
            if self.height > max_size: self.height = max_size

        return True

    def draw(self, context):

        lcol = self.layout.column(align=False)

        split_val = 0.4

        row = split_layout(lcol, split_val)
        right_aligned_label(row, 'Name:')
        row.prop(self, 'name', text='')

        BaseOperator.draw_base_image_settings(self, lcol, split_val, show_interpolation=False)

        row = split_layout(lcol, split_val)
        right_aligned_label(row, 'UV Map:')
        row.prop_search(self, "uv_map", self, "uv_map_coll", text='', icon='GROUP_UVS')

        row = split_layout(lcol, split_val)
        right_aligned_label(row, 'Samples:')
        row.prop(self, 'samples', text='')

        row = split_layout(lcol, split_val)
        right_aligned_label(row, 'Margin:')
        if is_bl_newer_than(3, 1):
            split = split_layout(row, 0.4, align=True)
            split.prop(self, 'margin', text='')
            split.prop(self, 'margin_type', text='')
        else:
            row.prop(self, 'margin', text='')

        lcol.separator()

        row = split_layout(lcol, split_val)
        row.label(text='')
        rrow = row.row(align=True)
        rrow.prop(self, 'blur')
        if self.blur:
            rrow.prop(self, 'blur_type', text='')

            row = split_layout(lcol, split_val)
            if self.blur_type == 'NOISE':
                right_aligned_label(row, 'Blur Factor:')
            else: right_aligned_label(row, 'Blur Size:')

            if self.blur_type == 'NOISE':
                row.prop(self, 'blur_factor', text='')
            else: row.prop(self, 'blur_size', text='')

            lcol.separator()

        row = split_layout(lcol, split_val)
        row.label(text='')
        row.prop(self, 'fxaa')

        if is_bl_newer_than(2, 81):
            row = split_layout(lcol, split_val)
            row.label(text='')
            row.prop(self, 'denoise', text='Use Denoise')

        # NOTE: Duplicate entity currently only available for mask
        if self.mask:
            row = split_layout(lcol, split_val)
            row.label(text='')
            row.prop(self, 'duplicate_entity', text='Duplicate Mask')

        if self.duplicate_entity:
            row = split_layout(lcol, split_val)
            row.label(text='')
            if self.mask:
                row.prop(self, 'disable_current', text='Disable Current Mask')
            else: row.prop(self, 'disable_current', text='Disable Current Layer')

        row = split_layout(lcol, split_val)
        row.label(text='')
        row.prop(self, 'use_image_atlas')

        if is_bl_newer_than(2, 80):
            lcol.separator()
            row = split_layout(lcol, split_val)
            right_aligned_label(row, 'Bake Device:')
            row.prop(self, 'bake_device', text='')

    def execute(self, context):
        if not self.execute_operator_prep(context): return {'CANCELLED'}

        if not self.layer:
            self.report({'ERROR'}, "Invalid context!")
            return self.execute_operator_cancelled(context)

        #if self.layer and not self.mask:
        #    self.report({'ERROR'}, "This feature is not implemented yet!")
        #    return self.execute_operator_cancelled(context)

        if self.uv_map == '':
            self.report({'ERROR'}, "UV Map cannot be empty!")
            return self.execute_operator_cancelled(context)

        if self.mask and self.mask.type == 'BACKFACE':
            self.report({'ERROR'}, "Backface mask can't be baked!")
            return self.execute_operator_cancelled(context)

        T = time.time()
        node = get_active_ypaint_node()
        yp = node.node_tree.yp
        tree = node.node_tree
        layer_tree = get_tree(self.layer)

        # Entity checking
        entity = self.mask if self.mask else self.layer
        entity_label = mask_type_labels[entity.type] if self.mask else layer_type_labels[entity.type]

        # Get bake properties
        bprops = get_bake_properties_from_self(self)

        # Bake entity to image
        rdict = bake_entity_as_image(entity, bprops, set_image_to_entity=not self.duplicate_entity)

        if rdict['message'] != '':
            self.report({'ERROR'}, rdict['message'])
            return self.execute_operator_cancelled(context)

        image = rdict['image']
        segment = rdict['segment']

        # Duplicate entity
        if self.duplicate_entity:

            if self.mask:

                # Disable source mask
                if self.mask and self.disable_current:
                    self.mask.enable = False

                # New entity name
                new_entity_name = get_unique_name(self.name, self.entities) if self.use_image_atlas else image.name

                # Create new mask
                mask = mask_common.add_new_mask(
                    self.layer, new_entity_name, 'IMAGE', 'UV', self.uv_map, 
                    image=image, vcol_name='', segment=segment
                )

                # Set mask properties
                mask.intensity_value = self.mask.intensity_value
                mask.blend_type = self.mask.blend_type
                for i, c in enumerate(self.mask.channels):
                    mask.channels[i].enable = c.enable

                # Reorder index
                self.layer.masks.move(len(self.layer.masks)-1, self.index+1)
                check_mask_mix_nodes(self.layer, layer_tree)
                check_mask_source_tree(self.layer) #, bump_ch)
                mask = self.layer.masks[self.index+1]

                if segment:
                    ImageAtlas.set_segment_mapping(mask, segment, image)
                    mask.segment_name = segment.name

                # Refresh uv
                refresh_temp_uv(context.object, mask)

                # Refresh Neighbor UV resolution
                set_uv_neighbor_resolution(mask)

                # Make new mask active
                self.mask = mask

            else:
                # TODO: Duplicate layer as image(s)
                pass

        # Make current entity active to update image
        if self.mask:
            self.mask.active_edit = True
        elif get_layer_index(self.layer) == yp.active_layer_index:
            yp.active_layer_index = yp.active_layer_index

        reconnect_layer_nodes(self.layer)
        rearrange_layer_nodes(self.layer)

        reconnect_yp_nodes(node.node_tree)
        rearrange_yp_nodes(node.node_tree)

        # Expand entity source to show rebake button
        ypui = context.window_manager.ypui
        if self.mask and not self.duplicate_entity:
            self.mask.expand_content = True
            self.mask.expand_source = True
        ypui.need_update = True

        if image: 
            self.report({'INFO'}, 'Baking '+entity_label+' is done in '+'{:0.2f}'.format(time.time() - T)+' seconds!')

        return self.execute_operator_finished(context)

class YRemoveBakedEntity(bpy.types.Operator):
    bl_idname = "wm.y_remove_baked_entity"
    bl_label = "Remove Baked Layer/Mask"
    bl_description = "Remove baked layer/mask"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return get_active_ypaint_node() and context.object.type == 'MESH'

    def execute(self, context):

        obj = context.object
        ypup = get_user_preferences()
        node = get_active_ypaint_node()
        yp = node.node_tree.yp

        entity = context.entity
        layer = None
        mask = None

        # Check entity
        m1 = re.match(r'^yp\.layers\[(\d+)\]$', entity.path_from_id())
        m2 = re.match(r'^yp\.layers\[(\d+)\]\.masks\[(\d+)\]$', entity.path_from_id())

        tree = None
        baked_source = None
        if m1: 
            layer = yp.layers[int(m1.group(1))]
            mask = None
            tree = get_source_tree(layer)
            baked_source = tree.nodes.get(layer.baked_source)
        elif m2: 
            layer = yp.layers[int(m2.group(1))]
            mask = layer.masks[int(m2.group(2))]
            tree = get_mask_tree(mask)
            baked_source = tree.nodes.get(mask.baked_source)
        else: 
            self.report({'ERROR'}, "Invalid context!")
            return {'CANCELLED'}

        if not baked_source:
            self.report({'ERROR'}, "No baked source found!")
            return {'CANCELLED'}

        image = baked_source.image if baked_source else None

        # Remove segment
        if image and entity.baked_segment_name != '':
            if image.yia.is_image_atlas:
                segment = image.yia.segments.get(entity.baked_segment_name)
                segment.unused = True
            elif image.yua.is_udim_atlas:
                UDIM.remove_udim_atlas_segment_by_name(image, entity.baked_segment_name, yp=yp)

            # Remove baked segment name since the data is removed
            entity.baked_segment_name = ''

        # Remove baked source
        remove_node(tree, entity, 'baked_source')
        entity.use_baked = False

        # Remove baked mapping
        layer_tree = get_tree(layer)
        remove_node(layer_tree, entity, 'baked_mapping')

        return {'FINISHED'}

class YRebakeBakedImages(bpy.types.Operator, BaseBakeOperator):
    bl_idname = "wm.y_rebake_baked_images"
    bl_label = "Rebake All Baked Images"
    bl_description = "Rebake all baked images used by all layers and masks"
    bl_options = {'REGISTER'}

    @classmethod
    def poll(cls, context):
        return get_active_ypaint_node() and context.object.type == 'MESH'

    def invoke(self, context, event):
        if get_user_preferences().skip_property_popups and not event.shift:
            return self.execute(context)

        return context.window_manager.invoke_props_dialog(self, width=320)

    def draw(self, context):
        self.layout.label(text='Rebaking all baked images can take a while to process', icon='ERROR')
    
    def execute(self, context): 
        if not self.execute_operator_prep(context): return {'CANCELLED'}

        T = time.time()
        node = get_active_ypaint_node()
        yp = node.node_tree.yp

        baked_counts = rebake_baked_images(yp)

        if baked_counts == 0:
            self.report({'ERROR'}, 'No baked layer/mask used!')
            return self.execute_operator_cancelled(context)

        self.report({'INFO'}, 'Rebaking all baked layers & masks is done in '+'{:0.2f}'.format(time.time() - T)+' seconds!')

        return self.execute_operator_finished(context)

class YRebakeSpecificLayers(bpy.types.Operator, BaseBakeOperator):
    bl_idname = "wm.y_rebake_specific_layers"
    bl_label = "Rebake Specific Layers"
    bl_description = "Rebake specific layers (FOR INTERNAL USE ONLY)"
    bl_options = {'REGISTER'}

    layer_ids = StringProperty(
        name = 'Layer Indices',
        description = 'Layer indices in form of list of integer converted to string',
        default=''
    )

    @classmethod
    def poll(cls, context):
        return get_active_ypaint_node() and context.object.type == 'MESH'

    def execute(self, context): 
        if not self.execute_operator_prep(context): return {'CANCELLED'}

        T = time.time()
        node = get_active_ypaint_node()
        yp = node.node_tree.yp

        layers = []
        if self.layer_ids != '':
            import ast
            ids = ast.literal_eval(self.layer_ids)
            layers = [l for i, l in enumerate(yp.layers) if i in ids]

        rebake_baked_images(yp, specific_layers=layers)

        return self.execute_operator_finished(context)

class YSelectAllOtherObjects(bpy.types.Operator):
    bl_idname = "wm.y_select_all_other_objects"
    bl_label = "Select All Other Objects"
    bl_description = "Select all objects in the other objects list"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return get_active_ypaint_node() and hasattr(context, 'bake_info')

    def execute(self, context):
        bpy.ops.object.select_all(action='DESELECT')

        for i in range(len(context.bake_info.other_objects)):
            so = context.bake_info.other_objects[i]
            if so.object:
                so_object = so.object
                if is_bl_newer_than(2, 80):
                    so_object.hide_viewport = False
                else: set_object_hide(so_object, False)
                so_object.hide_render = False
                set_object_select(so_object, True)
        if so_object:
            set_active_object(so_object)

        return {'FINISHED'}

class YToggleOtherObjectsVisibility(bpy.types.Operator):
    bl_idname = "wm.y_toggle_other_objects_visibility"
    bl_label = "Toggle Other Objects Visibility"
    bl_description = "Toggle visibility of all objects in the other objects list"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return get_active_ypaint_node() and hasattr(context, 'bake_info')

    def execute(self, context):
        bi = context.bake_info

        reference_obj = None
        for oo in bi.other_objects:
            if oo.object:
                reference_obj = oo.object
                break

        if not reference_obj:
            return {'CANCELLED'}

        current_hidden_state = reference_obj.hide_viewport if is_bl_newer_than(2, 80) else get_object_hide(reference_obj)

        for oo in bi.other_objects:
            if oo.object:
                if is_bl_newer_than(2, 80):
                    oo.object.hide_viewport = not current_hidden_state
                else: set_object_hide(oo.object, not current_hidden_state)
                oo.object.hide_render = not current_hidden_state

        return {'FINISHED'}

classes = (
    YBakeToLayer,
    YBakeEntityToImage,
    YRemoveBakeInfoOtherObject,
    YTryToSelectBakedVertexSelect,
    YRemoveBakedEntity,
    YRebakeBakedImages,
    YRebakeSpecificLayers,
    YSelectAllOtherObjects,
    YToggleOtherObjectsVisibility,
)

def register():
    for cls in classes: bpy.utils.register_class(cls)

def unregister():
    for cls in classes: bpy.utils.unregister_class(cls)
