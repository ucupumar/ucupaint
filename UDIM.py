import bpy, numpy, os, tempfile, shutil
from bpy.props import *
from .common import *
from . import lib, BakeInfo

UDIM_DIR = 'UDIM__'
UV_TOLERANCE = 0.1

def is_udim_supported():
    return is_greater_than_340()

def fill_tiles(image, color=None, width=0, height=0, empty_only=False):
    if image.source != 'TILED': return
    if color == None: color = image.yui.base_color
    for tile in image.tiles:
        fill_tile(image, tile.number, color, width, height, empty_only)

def fill_tile(image, tilenum, color=None, width=0, height=0, empty_only=False):
    if image.source != 'TILED': return False
    if color == None: color = image.yui.base_color
    tile = image.tiles.get(tilenum)
    new_tile = False
    # HACK: For some reason 1001 tile is always exists when using get
    # Check if it actually exists by comparing the returned tile number
    if not tile or tile.number != tilenum:
        tile = image.tiles.new(tile_number=tilenum)
        new_tile = True

    # If tile is still not created even after creating new one
    if not tile: return False

    if tile.size[0] == 0 or tile.size[1] == 0:
        new_tile = True

    image.tiles.active = tile

    if not new_tile and empty_only: return False

    if width == 0: width = tile.size[0]
    if height == 0: height = tile.size[1]
    if width == 0: width = 1024
    if height == 0: height = 1024

    # NOTE: Override operator won't work on Blender 4.0
    #override = bpy.context.copy()
    #override['edit_image'] = image
    #bpy.ops.image.tile_fill(override, color=color, width=width, height=height, float=image.is_float, alpha=True)

    color_str = '('
    color_str += str(color[0]) + ', '
    color_str += str(color[1]) + ', '
    color_str += str(color[2]) + ', '
    color_str += str(color[3]) + ')'

    print('UDIM: Filling tile ' + str(tilenum) + ' with color ' + color_str)

    # Fill tile
    ori_ui_type = bpy.context.area.ui_type
    bpy.context.area.ui_type = 'IMAGE_EDITOR'
    bpy.context.space_data.image = image
    bpy.ops.image.tile_fill(color=color, width=width, height=height, float=image.is_float, alpha=True)
    bpy.context.area.ui_type = ori_ui_type

    return True

def copy_udim_pixels(src, dest):
    for tile in src.tiles:
        # Check if tile number exists on both images and has same sizes
        dtile = dest.tiles.get(tile.number)
        if not dtile: continue
        if tile.size[0] != dtile.size[0] or tile.size[1] != dtile.size[1]: continue

        # Swap first
        if tile.number != 1001:
            swap_tile(src, 1001, tile.number)
            swap_tile(dest, 1001, tile.number)

        # Set pixels
        dst.pixels = list(src.pixels)

        # Swap back
        if tile.number != 1001:
            swap_tile(src, 1001, tile.number)
            swap_tile(dest, 1001, tile.number)

def get_tile_numbers(objs, uv_name):

    tiles = [1001]

    if not is_udim_supported(): return tiles

    T = time.time()

    # Get active object
    obj = bpy.context.object
    ori_mode = 'OBJECT'
    if obj in objs and obj.mode != 'OBJECT':
        ori_mode = obj.mode
        bpy.ops.object.mode_set(mode='OBJECT')

    arr = numpy.empty(0, dtype=numpy.float32)

    # Get all uv coordinates
    for o in objs:
        uv = o.data.uv_layers.get(uv_name)
        if not uv: continue
    
        uv_arr = numpy.zeros(len(o.data.loops)*2, dtype=numpy.float32)
        uv.data.foreach_get('uv', uv_arr)
        arr = numpy.append(arr, uv_arr)

    # Reshape the array to 2D
    arr.shape = (arr.shape[0]//2, 2)

    # Tolerance to skip value around x.0
    trange = [UV_TOLERANCE/2.0, 1.0-(UV_TOLERANCE/2.0)]
    arr = arr[((arr[:,0]-(numpy.floor(arr[:,0]))) >= trange[0]) &
              ((arr[:,0]-(numpy.floor(arr[:,0]))) <= trange[1]) & 
              ((arr[:,1]-(numpy.floor(arr[:,1]))) >= trange[0]) &
              ((arr[:,1]-(numpy.floor(arr[:,1]))) <= trange[1])]

    # Floor array to integer
    arr = numpy.floor(arr).astype(int)

    # Get unique value only
    arr = numpy.unique(arr, axis=0)
    
    # Get the udim representation
    for i in arr:

        # UV value can only be within 0 .. 10 range
        u = min(max(i[0], 0), 10)
        v = min(max(i[1], 0), 100)

        # Calculate the tile
        tile = 1001 + u + v*10
        if tile not in tiles:
            tiles.append(tile)
    
    if ori_mode != 'OBJECT':
        bpy.ops.object.mode_set(mode=ori_mode)

    print('INFO: Getting tile numbers are done at', '{:0.2f}'.format((time.time() - T) * 1000), 'ms!')
        
    return tiles

def is_uvmap_udim(objs, uv_name):

    if not is_udim_supported(): return False

    T = time.time()

    # Get active object
    obj = bpy.context.object
    ori_mode = 'OBJECT'
    if obj in objs and obj.mode != 'OBJECT':
        ori_mode = obj.mode
        bpy.ops.object.mode_set(mode='OBJECT')

    arr = numpy.empty(0, dtype=numpy.float32)

    # Get all uv coordinates
    for o in objs:
        uv = o.data.uv_layers.get(uv_name)
        if not uv: continue
    
        uv_arr = numpy.zeros(len(o.data.loops)*2, dtype=numpy.float32)
        uv.data.foreach_get('uv', uv_arr)
        arr = numpy.append(arr, uv_arr)

    if ori_mode != 'OBJECT':
        bpy.ops.object.mode_set(mode=ori_mode)

    is_udim = numpy.any(arr > 1.0 + UV_TOLERANCE/2)

    print('INFO: UDIM checking is done at', '{:0.2f}'.format((time.time() - T) * 1000), 'ms!')

    return is_udim

def get_temp_udim_dir():
    if bpy.data.filepath != '':
        directory = os.path.dirname(bpy.data.filepath)
        return os.path.join(directory, UDIM_DIR)

    return tempfile.gettempdir()

def is_using_temp_dir(image):
    directory = os.path.dirname(bpy.path.abspath(image.filepath))
    if directory == get_temp_udim_dir() or directory == tempfile.gettempdir():
        return True
    return False

def remove_udim_files_from_disk(image, directory, remove_dir=False, tilenum=-1):
    # Get filenames
    img_names = []
    filename = bpy.path.basename(image.filepath)
    prefix = filename.split('.<UDIM>.')[0]
    if os.path.isdir(directory):
        for f in os.listdir(directory):
            m = re.match(r'' + re.escape(prefix) + '\.(\d{4})\.*', f)
            if m:
                if tilenum != -1 and tilenum != int(m.group(1)): continue
                img_names.append(f)

    # Remove images
    for f in img_names:
        try: os.remove(os.path.join(directory, f))
        except Exception as e: print(e)

    # Remove directory
    if remove_dir and directory != tempfile.gettempdir() and len(os.listdir(directory)) == 0:
        try: os.rmdir(directory)
        except Exception as e: print(e)

def set_udim_filepath(image, filename, directory):
    filepath = os.path.join(directory, filename + '.<UDIM>.png')
    if directory != tempfile.gettempdir():
        try: filepath = bpy.path.relpath(filepath)
        except: pass
    #if not os.path.exists(directory):
    #    os.makedirs(directory)
    image.filepath = filepath

# UDIM need filepath to work, 
# So there's need to initialize filepath for every udim image created
def initial_pack_udim(image, base_color=None, filename=''):

    # Get temporary directory
    temp_dir = get_temp_udim_dir()

    # Check if image is already packed
    use_packed = False 
    if image.packed_file: use_packed = True

    # Check if image already use temporary filepath
    use_temp_dir = is_using_temp_dir(image)

    # Set temporary filepath
    if (image.filepath == '' or # Set image filepath if it's still empty
        not is_image_filepath_unique(image) # Force set new filepath when image filepath is not unique
        ):
        use_temp_dir = True
        filename = filename if filename != '' else image.name
        set_udim_filepath(image, filename, temp_dir)

    # When blend file is copied to another PC, there's a chance directory is missing
    directory = os.path.dirname(bpy.path.abspath(image.filepath))
    if not use_temp_dir and not os.path.isdir(directory):
        ori_ui_type = bpy.context.area.ui_type
        bpy.context.area.ui_type = 'IMAGE_EDITOR'
        bpy.context.space_data.image = image
        path = temp_dir + os.sep + image.name + '.<UDIM>.png'
        bpy.ops.image.save_as(filepath=path , relative_path=True)
        bpy.context.area.ui_type = ori_ui_type
        use_temp_dir = True

    # Save then pack
    image.save()
    if use_packed or use_temp_dir:
        image.pack()

    # Remove temporary files
    if use_temp_dir:
        remove_udim_files_from_disk(image, temp_dir, True)

    # Remember base color
    if base_color:
        image.yui.base_color = base_color

def swap_tiles(image, swap_dict, reverse=False):

    # Directory of image
    directory = os.path.dirname(bpy.path.abspath(image.filepath))

    # Remember stuff
    ori_packed = False
    if image.packed_file: ori_packed = True

    # Image saved flag
    image_saved = False

    iterator = reversed(swap_dict) if reverse else swap_dict

    for tilenum0 in iterator:

        tilenum1 = swap_dict[tilenum0]

        tile0 = image.tiles.get(tilenum0)
        tile1 = image.tiles.get(tilenum1)

        if not tile0 or not tile1: continue
        if tilenum0 == tilenum1: continue

        # Save the image first
        if not image_saved:
            image.save()
            image_saved = True

        print('UDIM: Swapping tile', tilenum0, 'to', tilenum1)

        str0 = '.' + str(tilenum0) + '.'
        str1 = '.' + str(tilenum1) + '.'
        filename = bpy.path.basename(image.filepath)
        prefix = filename.split('.<UDIM>.')[0]

        # Get image paths
        path0 = ''
        path1 = ''
        for f in os.listdir(directory):
            m = re.match(r'' + re.escape(prefix) + '\.\d{4}\.*', f)
            if m:
                if str0 in f: path0 = os.path.join(directory, f)
                elif str1 in f: path1 = os.path.join(directory, f)

        # Swap paths
        temp_path = path0.replace(str0, '.xxxx.')
        os.rename(path0, temp_path)
        os.rename(path1, path0)
        os.rename(temp_path, path1)
    
    if image_saved:

        # Reload to update image
        image.reload()
        image.save()

        # Repack image
        if ori_packed:
            image.pack()

            # Remove file if they are using temporary directory
            if is_using_temp_dir(image):
                remove_udim_files_from_disk(image, directory, True)

def swap_tile(image, tilenum0, tilenum1):
    swap_dict = {}
    swap_dict[tilenum0] = tilenum1
    swap_tiles(image, swap_dict)

def copy_tiles(image0, image1, copy_dict):

    # Directory of images
    directory0 = os.path.dirname(bpy.path.abspath(image0.filepath))
    directory1 = os.path.dirname(bpy.path.abspath(image1.filepath))

    # Remember stuff
    ori0_packed = False
    ori1_packed = False
    if image0.packed_file: ori0_packed = True
    if image1.packed_file: ori1_packed = True

    # Image saved flag
    image_saved = False

    for tilenum0, tilenum1 in copy_dict.items():

        tile0 = image0.tiles.get(tilenum0)
        tile1 = image1.tiles.get(tilenum1)

        if not tile0 or not tile1: continue

        # Get image paths
        str0 = '.' + str(tilenum0) + '.'
        str1 = '.' + str(tilenum1) + '.'
        filename0 = bpy.path.basename(image0.filepath)
        filename1 = bpy.path.basename(image1.filepath)
        splits0 = filename0.split('.<UDIM>.')
        splits1 = filename1.split('.<UDIM>.')
        prefix0 = splits0[0]
        prefix1 = splits1[0]
        suffix0 = splits0[1]
        suffix1 = splits1[1]

        path0 = os.path.join(directory0, prefix0 + str0 + suffix0)
        path1 = os.path.join(directory1, prefix1 + str1 + suffix1)

        if suffix0 != suffix1: continue
        if path0 == path1: continue

        # Save the image first
        if not image_saved:
            image0.save()
            image1.save()
            image_saved = True

        print('UDIM: Copying tile', tilenum0, '(' + image0.name + ') to', tilenum1, '(' + image1.name + ')')

        # Copy and replace image
        if os.path.exists(path1):
            os.remove(path1)
        shutil.copyfile(path0, path1)

    if image_saved:

        # Reload to update image
        #image0.reload()
        image1.reload()
        #image0.save()
        image1.save()

        # Repack image 0
        if ori0_packed:
            image0.pack()

            # Remove file if they are using temporary directory
            if is_using_temp_dir(image0):
                remove_udim_files_from_disk(image0, directory0, True)

        # Repack image 1
        if ori1_packed:
            image1.pack()

            # Remove file if they are using temporary directory
            if is_using_temp_dir(image1):
                remove_udim_files_from_disk(image1, directory1, True)

def remove_tiles(image, tilenums):

    #print('UDIM: Removing tiles is starting...')

    # Directory of image
    directory = os.path.dirname(bpy.path.abspath(image.filepath))

    # Remember stuff
    ori_packed = False
    if image.packed_file: ori_packed = True

    # Image saved flag
    image_saved = False

    for tilenum in tilenums:
        tile = image.tiles.get(tilenum)
        if not tile: continue

        # Save the image first
        if not image_saved:
            image.save()
            image_saved = True

        print('UDIM: Removing tile', tilenum)

        # Remove tile
        image.tiles.remove(tile)

    # Repack image
    if image_saved:
        if ori_packed:
            image.pack()

            # Remove file if they are using temporary directory
            if is_using_temp_dir(image):
                remove_udim_files_from_disk(image, directory, True)
        else:
            # Remove file
            remove_udim_files_from_disk(image, directory, False, tilenum)

def remove_tile(image, tilenum):
    remove_tiles(image, [tilenum])

class YRefillUDIMTiles(bpy.types.Operator):
    bl_idname = "node.y_refill_udim_tiles"
    bl_label = "Refill UDIM Tiles"
    bl_description = "Refill all UDIM tiles used by all layers and masks based on their UV"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return get_active_ypaint_node()

    def execute(self, context):
        yp = context.layer.id_data.yp
        entities, images, segment_names = get_yp_entities_images_and_segments(yp)

        mat = get_active_material()

        refreshed_images = []

        for i, image in enumerate(images):
            if image.source != 'TILED': continue

            ents = entities[i]
            entity = ents[0]

            if image.yua.is_udim_atlas:
                if image not in refreshed_images:
                    refresh_udim_atlas(image, yp)
                    refreshed_images.append(image)

            else:
                # Get tile numbers based from uv
                uv_name = entity.uv_name
                objs = get_all_objects_with_same_materials(mat, True, uv_name)
                tilenums = get_tile_numbers(objs, uv_name)

                # Get width and height
                width = 1024
                height = 1024
                if image.size[0] != 0: width = image.size[0]
                if image.size[1] != 0: height = image.size[1]

                color = image.yui.base_color

                for tilenum in tilenums:
                    fill_tile(image, tilenum, color, width, height, empty_only=True)

                initial_pack_udim(image)

        return {'FINISHED'}

def udim_tilenum_items(self, context):
    image = bpy.data.images.get(self.image_name)

    if image.yua.is_udim_atlas:
        yp = get_active_ypaint_node().node_tree.yp
        layer = yp.layers.get(self.layer_name)

        # Get entity
        entity = layer
        mask_entity = False
        for mask in layer.masks:
            if mask.active_edit:
                entity = mask
                mask_entity = True
                break

        segment = image.yua.segments.get(entity.segment_name)

        tilenums = get_udim_segment_tilenums(segment)
    else:
        tilenums = [t.number for t in image.tiles]

    items = []

    for i, tilenum in enumerate(tilenums):
        items.append((str(tilenum), str(tilenum), '', 'IMAGE_DATA', i))

    return items

def get_udim_segment_index(image, segment):
    index = -1
    ids = [i for i, s in enumerate(image.yua.segments) if s == segment]
    if len(ids) > 0: index = ids[0]
    return index

def get_udim_segment_tilenums(segment):

    image = segment.id_data
    offset_y = get_udim_segment_mapping_offset(segment)

    tilenums = []
    for btile in segment.base_tiles:
        tilenum = btile.number + offset_y * 10
        tilenums.append(tilenum)

    return tilenums

def get_udim_segment_base_tilenums(segment):
    return [btile.number for btile in segment.base_tiles]

def set_udim_segment_mapping(entity, segment, image):

    offset_y = get_udim_segment_mapping_offset(segment)

    m1 = re.match(r'^yp\.layers\[(\d+)\]$', entity.path_from_id())
    m2 = re.match(r'^yp\.layers\[(\d+)\]\.masks\[(\d+)\]$', entity.path_from_id())

    if m1: mapping = get_layer_mapping(entity)
    else: mapping = get_mask_mapping(entity)

    if mapping: mapping.inputs[1].default_value[1] = offset_y

def create_udim_atlas(tilenums, name='', width=1024, height=1024, color=(0,0,0,0), colorspace='', hdr=False):
    if name != '':
        name = '~' + name + ' UDIM Atlas'
    else: name = '~UDIM Atlas'

    # Get offset based on max y value
    max_y = int((max(tilenums) - 1000) / 10)
    offset_y = max_y + 2

    name = get_unique_name(name, bpy.data.images)

    image = bpy.data.images.new(name=name, 
            width=width, height=height, alpha=True, float_buffer=hdr, tiled=True)
    image.yua.is_udim_atlas = True
    image.yui.base_color = color
    if colorspace != '': image.colorspace_settings.name = colorspace

    # Pack image
    initial_pack_udim(image)

    return image

def refresh_udim_segment_base_tilenums(segment, tilenums):
    # Add tiles
    for tilenum in tilenums:
        if str(tilenum) not in segment.base_tiles:
            btile = segment.base_tiles.add()
            btile.name = str(tilenum)
            btile.number = tilenum

    # Remove unused tiles
    for i, btile in reversed(list(enumerate(segment.base_tiles))):
        if btile.number not in tilenums:
            segment.base_tiles.remove(i)

def create_udim_atlas_segment(image, tilenums, width=1024, height=1024, color=(0,0,0,0), source_image=None, source_tilenums=[], yp=None):

    #if yp: refresh_udim_atlas(image, yp)

    atlas = image.yua
    name = get_unique_name('Segment', atlas.segments)

    segment = None

    segment = atlas.segments.add()
    segment.name = name
    segment.base_color = color
    refresh_udim_segment_base_tilenums(segment, tilenums)
    offset = get_udim_segment_mapping_offset(segment) * 10

    copy_dict = {}
    
    for i, tilenum in enumerate(tilenums):
        if source_image:
            if source_tilenums != []:
                source_tile = source_image.tiles.get(source_tilenums[i])
            else: source_tile = source_image.tiles.get(tilenum)
            width = source_tile.size[0]
            height = source_tile.size[1]
            if source_tilenums != []:
                copy_dict[source_tilenums[i]] = tilenum + offset
            else: copy_dict[tilenum] = tilenum + offset

        tilenum += offset
        fill_tile(image, tilenum, color, width, height, empty_only=False)

    # Copy from source image
    if source_image:
        copy_tiles(source_image, image, copy_dict)

    # Pack image
    initial_pack_udim(image)

    return segment

def is_tilenums_fit_in_udim_atlas(image, tilenums):
    max_y = int((max(tilenums) - 1000) / 10)
    atlas_tilenums = [t.number for t in image.tiles]
    if len(atlas_tilenums) > 0:
        atlas_max_y = int((max(atlas_tilenums) - 1000) / 10) + 1
    else: atlas_max_y = 0

    remains_y = 99 - atlas_max_y
    
    return remains_y > max_y

def get_set_udim_atlas_segment(tilenums, 
        width=1024, height=1024, color=(0,0,0,0), colorspace='', hdr=False, yp=None, 
        source_image=None, source_tilenums=[], 
        image_exception=None, image_inclusions=[]):

    ypup = get_user_preferences()
    segment = None

    # Get bunch of images
    if yp: #and ypup.unique_image_atlas_per_yp:
        images = get_yp_images(yp, udim_only=True)
        name = yp.id_data.name
    else:
        images = [img for img in bpy.data.images if img.source == 'TILED']
        name = ''

    # Extra images to be included
    for image in image_inclusions:
        if image not in images:
            images.append(image)

    for image in images:
        if image_exception and image == image_exception: continue
        if image.yua.is_udim_atlas and image.is_float == hdr and is_tilenums_fit_in_udim_atlas(image, tilenums):
            if colorspace != '' and image.colorspace_settings.name != colorspace: continue
            segment = create_udim_atlas_segment(image, tilenums, width, height, color, 
                    source_image=source_image, source_tilenums=source_tilenums, yp=yp)
        if segment:
            break

    if not segment:
        # If proper UDIM atlas can't be found, create new one
        image = create_udim_atlas(tilenums, name, width, height, color, colorspace, hdr)
        segment = create_udim_atlas_segment(image, tilenums, width, height, color, 
                source_image=source_image, source_tilenums=source_tilenums, yp=yp)

    return segment

def get_all_udim_atlas_tilenums(image, tilenums=[]):

    all_tilenums = []

    for segment in image.yua.segments:
        tilenums = get_udim_segment_tilenums(segment)
        all_tilenums.extend(tilenums)

    return all_tilenums

def rearrange_tiles(image, convert_dict):

    # Directory of images
    directory = os.path.dirname(bpy.path.abspath(image.filepath))

    # Remember stuff
    ori_packed = False
    if image.packed_file: ori_packed = True

    # Image saved flag
    image_saved = False

    already_renamed = []

    # First pass of renaming
    for tilenum0, tilenum1 in convert_dict.items():

        tile = image.tiles.get(tilenum0)
        if not tile: continue

        # Get image paths
        str0 = '.' + str(tilenum0) + '.'
        str1 = '.' + str(tilenum1) + '.'
        filename = bpy.path.basename(image.filepath)
        splits = filename.split('.<UDIM>.')
        prefix = splits[0]
        suffix = splits[1]

        path0 = os.path.join(directory, prefix + str0 + suffix)
        path1 = os.path.join(directory, prefix + str1 + suffix)

        # Save the image first
        if not image_saved:
            image.save()
            image_saved = True

        print('UDIM: Rename tile', tilenum0, 'to', tilenum1, '(' + image.name + ')')

        # Copy and replace image
        if os.path.exists(path1):
            if tilenum1 in convert_dict:
                path1 += '.TEMP_NAME'
            else: os.remove(path1)

        shutil.copyfile(path0, path1)
        #os.rename(path0, path1)

    # Second pass is removing temporary name suffix
    if os.path.isdir(directory):

        temp_names = []
        ori_names = []

        for f in os.listdir(directory):
            if f.endswith('.TEMP_NAME'):
                temp_names.append(f)
                ori_names.append(f.split('.TEMP_NAME')[0])

        for i, temp_name in enumerate(temp_names):
            temp_path = os.path.join(directory, temp_name)
            ori_path = os.path.join(directory, ori_names[i])
            if os.path.exists(ori_path):
                os.remove(ori_path)
            os.rename(temp_path, ori_path)

    if image_saved:

        # Reload to update image
        image.reload()
        image.save()

        # Repack image
        if ori_packed:
            image.pack()

            # Remove file if they are using temporary directory
            if is_using_temp_dir(image):
                remove_udim_files_from_disk(image, directory, True)

def refresh_udim_atlas(image, yp=None, check_uv=True, remove_index=-1):
    T = time.time()

    # Actual tilenums from the image
    cur_tilenums = [t.number for t in image.tiles]

    if not yp: yp = get_active_ypaint_node().node_tree.yp

    entities = get_yp_entites_using_same_image(yp, image)

    # Create conversion dict
    convert_dict = {}
    uv_tilenums_dict = {}
    new_tilenums_dict = {}
    out_of_bound_segment_names = []

    ori_offset_y = 0
    new_offset_y = 0
    for i, segment in enumerate(image.yua.segments):

        # Get original base tilenums
        ori_tilenums = new_tilenums = get_udim_segment_base_tilenums(segment)

        # Get UV name
        if check_uv:
            uv_name = ''
            ents = [ent for ent in entities if ent.segment_name == segment.name]
            if ents: uv_name = ents[0].uv_name

            # Get new tilenums based on uv
            if uv_name != '':
                if uv_name not in uv_tilenums_dict:
                    mat = get_active_material()
                    objs = get_all_objects_with_same_materials(mat, True, uv_name)
                    new_tilenums = uv_tilenums_dict[uv_name] = get_tile_numbers(objs, uv_name)
                else: new_tilenums = uv_tilenums_dict[uv_name]

        # Remember new tilenums
        new_tilenums_dict[segment.name] = new_tilenums

        # Skip for to be removed index
        if i != remove_index:

            # Fill conversion dict
            tile_convert_dict = {}
            out_of_bound = False
            for nt in new_tilenums:
                new_index = nt + new_offset_y * 10
                if new_index > 2000:
                    out_of_bound = True
                else:
                    if nt in ori_tilenums:
                        ori_index = nt + ori_offset_y * 10
                        if ori_index != new_index:
                            tile_convert_dict[ori_index] = new_index

            if out_of_bound:
                out_of_bound_segment_names.append(segment.name)
            else:
                convert_dict.update(tile_convert_dict)

        # Add tilenums height to original offset
        ori_offset_y += get_tilenums_height(ori_tilenums) + 1

        # Skip for to be removed index
        if i != remove_index:

            # Add tilenums height to new offset
            new_offset_y += get_tilenums_height(new_tilenums) + 1

    # If there are out of bound segments, create new segments
    oob_dict = {}
    new_atlas_images = []
    for name in out_of_bound_segment_names:
        segment = image.yua.segments.get(name)
        segment_base_tilenums = get_udim_segment_base_tilenums(segment)
        segment_tilenums = get_udim_segment_tilenums(segment)
        new_segment = get_set_udim_atlas_segment(segment_base_tilenums, color=segment.base_color, 
                colorspace=image.colorspace_settings.name, hdr=image.is_float, yp=yp,
                source_image=image, source_tilenums=segment_tilenums,
                image_exception=image, image_inclusions=new_atlas_images)

        oob_dict[name] = new_segment
        if new_segment.id_data not in new_atlas_images:
            new_atlas_images.append(new_segment.id_data)

    # Remove out of bound segments
    for name in out_of_bound_segment_names:
        segment = image.yua.segments.get(name)
        index = get_udim_segment_index(image, segment)
        image.yua.segments.remove(index)

    # If remove index exists
    if remove_index != -1:
        image.yua.segments.remove(remove_index)

    # Set new tilenums
    for segment in image.yua.segments:
        new_tilenums = new_tilenums_dict[segment.name]
        refresh_udim_segment_base_tilenums(segment, new_tilenums)

        # Check for out of bounds segments
        #segment_tilenums = get_udim_segment_tilenums(segment)

    # Extend tilenums
    tilenums = get_all_udim_atlas_tilenums(image)

    # Fill tiles
    dirty = False
    for tilenum in tilenums:
        if fill_tile(image, tilenum, empty_only=True):
            dirty = True

    # Pack after fill
    if dirty: initial_pack_udim(image)

    # Rearrange tiles
    rearrange_tiles(image, convert_dict)

    # Remove unused tilenum
    unused_tilenums = [tile.number for tile in image.tiles if tile.number not in tilenums and tile.number != 1001]
    remove_tiles(image, unused_tilenums)

    # Refresh entities mapping
    for entity in entities:
        if entity.segment_name != '':
            if entity.segment_name in oob_dict: 
                # Set entity that are using newly create segment on other image
                source = get_entity_source(entity)
                source.image = new_segment.id_data
                entity.segment_name = new_segment.name
                set_udim_segment_mapping(entity, new_segment, new_segment.id_data)
            else:
                segment = image.yua.segments.get(entity.segment_name)
                if segment: set_udim_segment_mapping(entity, segment, image)

    # Also refresh newly created atlas images
    for new_image in new_atlas_images:
        refresh_udim_atlas(new_image, yp=yp, check_uv=check_uv, remove_index=remove_index)

    print('INFO: UDIM Atlas offsets are refreshed at', '{:0.2f}'.format((time.time() - T) * 1000), 'ms!')

    return image

def remove_udim_atlas_segment_by_name(image, segment_name, yp=None):
    T = time.time()

    if not yp: yp = get_active_ypaint_node().node_tree.yp

    index = [i for i, s in enumerate(image.yua.segments) if s.name == segment_name]
    if len(index) == 0: return
    index = index[0]

    refresh_udim_atlas(image, yp, check_uv=False, remove_index=index)

    print('INFO: UDIM Atlas segment is removed at', '{:0.2f}'.format((time.time() - T) * 1000), 'ms!')

def remove_udim_atlas_segment_by_index(image, index, yp=None):
    if not yp: yp = get_active_ypaint_node().node_tree.yp
    try: segment = image.yua.segments[index]
    except: return
    remove_udim_atlas_segment_by_name(image, segment.name, yp)

class YNewUDIMAtlasSegmentTest(bpy.types.Operator):
    bl_idname = "image.y_new_udim_atlas_segment_test"
    bl_label = "New UDIM Atlas Segment Test"
    bl_description = "New UDIM Atlas segment test"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return True

    def execute(self, context):
        mat = get_active_material()
        obj = context.object
        uv_name = obj.data.uv_layers.active.name

        objs = get_all_objects_with_same_materials(mat, True, uv_name)
        tilenums = get_tile_numbers(objs, uv_name)

        new_segment = get_set_udim_atlas_segment(tilenums, 1024, 1024, color=(0,0,0,0), colorspace='sRGB', hdr=False)

        image = new_segment.id_data

        area = context.area
        if hasattr(area.spaces[0], 'image'):
            area.spaces[0].image = image

        return {'FINISHED'}

class YRefreshUDIMAtlasOffset(bpy.types.Operator):
    bl_idname = "image.y_refresh_udim_atlas_offset"
    bl_label = "Refresh UDIM Atlas Offset"
    bl_description = "Refresh UDIM Atlas offset based on current UV islands"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return True

    def execute(self, context):
        mat = get_active_material()
        uv_name = 'UVMap'

        area = context.area
        image = area.spaces[0].image
        if not image.yua.is_udim_atlas: return {'CANCELLED'}

        refresh_udim_atlas(image)

        return {'FINISHED'}

class YRemoveUDIMAtlasSegment(bpy.types.Operator):
    bl_idname = "image.y_remove_udim_atlas_segment"
    bl_label = "Remove UDIM Atlas Segment"
    bl_description = "Remove UDIM Atlas segment"
    bl_options = {'REGISTER', 'UNDO'}

    index : IntProperty(
        name="Segment Index",
        description="UDIM Atlas Segment Index",
        default=0
    )

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=320)

    def draw(self, context):
        col = self.layout.column()
        col.prop(self, "index")

    def execute(self, context):
        mat = get_active_material()
        uv_name = 'UVMap'

        area = context.area
        image = area.spaces[0].image
        if not image.yua.is_udim_atlas: return {'CANCELLED'}

        # Remove segment
        remove_udim_atlas_segment_by_index(image, self.index)

        return {'FINISHED'}

class Y_PT_UDIM_Atlas_menu(bpy.types.Panel):
    bl_label = "UDIM Atlas"
    bl_space_type = "IMAGE_EDITOR"
    bl_region_type = "UI"
    bl_category = "Image"

    @classmethod
    def poll(cls, context):
        return True

    def draw(self, context):
        c = self.layout.column()
        c.operator('image.y_new_udim_atlas_segment_test', icon_value=lib.get_icon('image'))
        c.operator('image.y_refresh_udim_atlas_offset', icon_value=lib.get_icon('image'))
        c.operator('image.y_remove_udim_atlas_segment', icon_value=lib.get_icon('image'))

class YUDIMAtlasSegmentTile(bpy.types.PropertyGroup):
    name : StringProperty(default='1001')
    number : IntProperty(default=1001, min=1001, max=2000)

class YUDIMAtlasSegment(bpy.types.PropertyGroup):

    name : StringProperty(
            name='Name',
            description='Name of UDIM Atlas Segments',
            default='')

    unused : BoolProperty(default=False)

    bake_info : PointerProperty(type=BakeInfo.YBakeInfoProps)
    base_color : FloatVectorProperty(subtype='COLOR', size=4, min=0.0, max=1.0, default=(0.0, 0.0, 0.0, 0.0))

    base_tiles : CollectionProperty(type=YUDIMAtlasSegmentTile)

class YUDIMAtlas(bpy.types.PropertyGroup):
    name : StringProperty(
            name='Name',
            description='Name of UDIM Atlas',
            default='')

    is_udim_atlas : BoolProperty(default=False)

    segments : CollectionProperty(type=YUDIMAtlasSegment)

class YUDIMInfo(bpy.types.PropertyGroup):
    base_color : FloatVectorProperty(subtype='COLOR', size=4, min=0.0, max=1.0, default=(0.0, 0.0, 0.0, 0.0))

def register():
    bpy.utils.register_class(YRefillUDIMTiles)
    bpy.utils.register_class(YNewUDIMAtlasSegmentTest)
    bpy.utils.register_class(YRefreshUDIMAtlasOffset)
    bpy.utils.register_class(YRemoveUDIMAtlasSegment)
    #bpy.utils.register_class(Y_PT_UDIM_Atlas_menu)
    bpy.utils.register_class(YUDIMAtlasSegmentTile)
    bpy.utils.register_class(YUDIMAtlasSegment)
    bpy.utils.register_class(YUDIMAtlas)
    bpy.utils.register_class(YUDIMInfo)

    bpy.types.Image.yua = PointerProperty(type=YUDIMAtlas)
    bpy.types.Image.yui = PointerProperty(type=YUDIMInfo)

def unregister():
    bpy.utils.unregister_class(YRefillUDIMTiles)
    bpy.utils.unregister_class(YNewUDIMAtlasSegmentTest)
    bpy.utils.unregister_class(YRefreshUDIMAtlasOffset)
    bpy.utils.unregister_class(YRemoveUDIMAtlasSegment)
    #bpy.utils.unregister_class(Y_PT_UDIM_Atlas_menu)
    bpy.utils.unregister_class(YUDIMAtlasSegmentTile)
    bpy.utils.unregister_class(YUDIMAtlasSegment)
    bpy.utils.unregister_class(YUDIMAtlas)
    bpy.utils.unregister_class(YUDIMInfo)
