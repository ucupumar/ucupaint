import shutil
import subprocess
from bpy.types import Context
from .common import * 
from .preferences import * 
from . import lib, Layer, Mask
from bpy.props import *
from bpy.types import PropertyGroup, Panel, Operator, UIList, Scene

import bpy

# export shader, choose location, save file
class ExportShader(Operator):
    """Export to godot shader"""

    bl_label = "Export Shader"
    bl_idname = "godot.export"

    filepath: StringProperty(subtype='FILE_PATH', options={'SKIP_SAVE'})

    use_shortcut = True
    shader_generation_test = True

    godot_directory = "/home/bocilmania/Documents/projects/godot/witch/"

    script_template = '''
shader_type spatial;
{0}vec4 layer(vec4 foreground, vec4 background) {{
    return foreground * foreground.a + background * (1.0 - foreground.a);
}}

void fragment() {{ 
{1}
    ALBEDO = albedo_all.rgb;
}}

'''

    script_vars = '''
uniform sampler2D {0};
uniform vec2 {1} = vec2({2},{3}); 
'''
    script_vars_roughness = "uniform sampler2D {}_roughness;\n"

    script_vars_normal = "uniform sampler2D {}_normal;\n"

    script_mask_vars = "uniform sampler2D {0};"
    
    script_fragment_var = '''
    vec2 scaled_uv_{0} = UV * {1};
    vec4 albedo_{0} = texture({2}, scaled_uv_{0});'''

    script_mask_fragment_var = '''
    vec4 mask_{0} = texture({1}, UV);
    albedo_{0}.a = mask_{0}.r;
'''

    script_albedo_combine_0 = '''

    vec4 albedo_all = layer(albedo_0, albedo_1);'''

    script_albedo_combine_next = '''
    albedo_all = layer(albedo_all, albedo_{0});
'''


    script_roughness_combine_0 = '''

    vec4 roughness_all = layer(roughness_{0}, roughness_{1});'''

    script_roughness_combine_next = '''
    roughness_all = layer(roughness_all, roughness_{0});
'''
    script_roughness_fragment = '''
    vec4 roughness_texture_channel = vec4(0.33, 0.33, 0.33, 0.0);
    float rough = dot(roughness_all, roughness_texture_channel);

    ROUGHNESS = rough;
'''
  #vec4 albedo = texture({1}, scaled_uv_{0});

    def get_godot_directory(self, path:str):

        current_dir = os.path.dirname(path)
        godot_project_dir = ""

        while godot_project_dir == "":
            for filename in os.listdir(current_dir):
                fl = os.path.join(current_dir, filename)
                if os.path.isfile(fl):
                    if filename == "project.godot":
                        godot_project_dir = current_dir
                        break
                    # print("check ", filename, " = ", fl)
            # move up directory

            parent_dir = os.path.dirname(current_dir)
            if parent_dir == current_dir:
                # print("break here ", current_dir)
                break
            current_dir = parent_dir
        print("godot project ", godot_project_dir)

        return godot_project_dir
    
    def fix_filename(self, filename:str):
        base, ext = os.path.splitext(filename)
        retval = filename

        if ext != ".gdshader":
            retval = base + ".gdshader"
        else:
            print("File extension is already .gdshader")

        print(f"File extension changed to: {retval}")
        return retval

    def execute(self, context):
        node = get_active_ypaint_node()
        yp = node.node_tree.yp

        print("====================================")
        index = 0
        layer:Layer.YLayer

        global_vars = ""
        fragment_vars = ""
        combine_content = ""

        # get directory of filepath
        my_directory = "/home/bocilmania/Documents/projects/godot/witch/models/box"
        # addon directory
        addon_dir = os.path.dirname(os.path.realpath(__file__))

        if self.use_shortcut:
            self.filepath = os.path.join(my_directory, "box.gdshader")
        else:
            my_directory = os.path.dirname(self.filepath)

        if not os.path.exists(my_directory):
            print("create directory ", my_directory)
            os.makedirs(my_directory)
        else:
            print("directory exist ", my_directory)

        self.godot_directory = self.get_godot_directory(self.filepath)

        if self.godot_directory == "":
            self.report({'ERROR'}, "This is not a godot directory")
            return {'CANCELLED'}

        self.filepath = self.fix_filename(self.filepath)

        print("save to ", self.filepath, " in ", self.godot_directory)

        base_arg = ["godot", "--headless", "--path", self.godot_directory]
        asset_args = []

        relative_path = os.path.relpath(self.filepath, self.godot_directory)
        relative_path = os.path.dirname(relative_path)
        
        print(f"Relative path: {relative_path}")


        roughness_overrides = []
        
        for layer_idx, layer in enumerate(yp.layers):
            if layer.enable:
                mapping = get_layer_mapping(layer)

                layer_var = "layer_"+str(index)

                scale_var = layer_var + "_scale"

                skala = mapping.inputs[3].default_value
                global_vars += self.script_vars.format(layer_var, scale_var, skala.x, skala.y)
                fragment_vars += self.script_fragment_var.format(index, scale_var, layer_var)

                source = get_layer_source(layer)

                image_path = source.image.filepath_from_user()

                asset_args.append(layer_var)
                asset_args.append(bpy.path.basename(image_path))

                # copy to directory 
                print("copy ", image_path, " to ", my_directory)
                shutil.copy(image_path, my_directory)

                yp = layer.id_data.yp

                channel:Layer.YLayerChannel
                for id_ch, channel in enumerate(layer.channels):
                    ch_name = yp.channels[id_ch].name
                    print("channel ", channel.name, " enable ", channel.enable, " name_", yp.channels[id_ch].name)
                    if channel.enable:
                        ch_image_path = ""
                        ch_image_path_1 = ""

                        if channel.override:
                            source_ch = get_channel_source(channel, layer)
                            ch_image_path = source_ch.image.filepath_from_user()
                    
                            print("channel path ", id_ch, " = ",ch_image_path)

                        if channel.override_1:
                            source_ch_1 = get_channel_source_1(channel, layer)
                            ch_image_path_1 = source_ch_1.image.filepath_from_user()
                           
                            print("channel path 1", id_ch, " = ",ch_image_path_1)

                        if ch_image_path != "":
                            shutil.copy(ch_image_path, my_directory)
                        if ch_image_path_1 != "":
                            shutil.copy(ch_image_path_1, my_directory)

                        if ch_name == "Roughness":
                            global_vars += self.script_vars_roughness.format(layer_var)
                            roughness_overrides.append(layer_idx)
                        elif ch_name == "Normal":
                            global_vars += self.script_vars_normal.format(layer_var)

                # print("filepath ", index, " = ",source.image.filepath_from_user())
                # print("rawpath ", index, " = ",source.image.filepath)
                # print("path user ", index, " = ",source.image.filepath_raw)
                msk:Mask.YLayerMask
                for idx, msk in enumerate(layer.masks):
                    mask_var = layer_var + "_mask_" + str(idx)
                    global_vars += self.script_mask_vars.format(mask_var)
                    fragment_vars += self.script_mask_fragment_var.format(index, mask_var)

                    mask_tree = get_mask_tree(msk)
                    mask_source = mask_tree.nodes.get(msk.source)

                    mask_image_path = mask_source.image.filepath_from_user()

                    if mask_image_path == "":
                        print("unpack item ", msk.name)
                        bpy.ops.file.unpack_item(id_name=msk.name, method='WRITE_ORIGINAL')
                        mask_image_path = mask_source.image.filepath_from_user()
                    else:
                        print("mask path exist ", mask_image_path)

                    asset_args.append(mask_var)
                    asset_args.append(bpy.path.basename(mask_image_path))

                    shutil.copy(mask_image_path, my_directory)
                    print("copy ", mask_image_path, " to ", my_directory)
                global_vars += "\n"

                if index == 1:
                    combine_content += self.script_albedo_combine_0
                elif index > 1:
                    combine_content += self.script_albedo_combine_next.format(index)
                    
                index += 1

        if len(roughness_overrides) > 0:
            if len(roughness_overrides) == 1:
                combine_content += '''
    vec4 roughness_all = roughness_{};
'''.format(roughness_overrides[0])
            for lyr_idx, lyr in enumerate(roughness_overrides):
                pass

        # print("parameter ", asset_args)
        fragment_vars += combine_content

        content_shader = self.script_template.format(global_vars, fragment_vars)

        print(content_shader)

        script_location = os.path.join(addon_dir, "godot4", "blender_import.gd")
        print("addon dir ", script_location)

        name_asset = bpy.path.display_name_from_filepath(self.filepath)

        print("file name", name_asset)

        if not self.shader_generation_test:
            file = open(self.filepath, "w")
            file.write(content_shader)
            file.close()

            all_params = base_arg + ["-s", script_location, "--", name_asset, relative_path] + asset_args
            print("all params=", " ".join(all_params))
            print(">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>")
            print(subprocess.run(base_arg + ["--import"], capture_output=True))
            print(">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>")
            print(subprocess.run(all_params, capture_output=True))
            print(subprocess.run(base_arg + ["--import"], capture_output=True))

        return {'FINISHED'}

    def invoke(self, context, event):
        if self.use_shortcut:
            return self.execute(context)
        else:
            context.window_manager.fileselect_add(self)
            return {'RUNNING_MODAL'}
    

classes = [ExportShader]

def register():
    for cl in classes:
        bpy.utils.register_class(cl)


def unregister():
    for cl in classes:
        bpy.utils.unregister_class(cl)
    

if __name__ == "__main__":
    register()