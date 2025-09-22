import bpy
import os, requests, time, threading, json
from bpy.props import PointerProperty, IntProperty
import bpy.utils.previews

from .common import get_addon_filepath, is_bl_newer_than, is_online, get_addon_title

class YSponsorProp(bpy.types.PropertyGroup):
    progress : IntProperty(
        default = 0,
        min = 0,
        max = 100,
        description = 'Progress of goal',
        subtype = 'PERCENTAGE'
    )

    expand_tiers : bpy.props.BoolVectorProperty(
        name = "Expand Tiers",
        description = "Expand Tiers List",
    )

    initialized : bpy.props.BoolProperty(
        default = False,
    )

    expanded : bpy.props.BoolProperty(
        default = True,
    )

class VIEW3D_PT_YPaint_support_ui(bpy.types.Panel):
    bl_label = "Support " + get_addon_title()
    bl_space_type = 'VIEW_3D'
    #bl_context = "object"
    bl_region_type = 'UI'
    bl_category = get_addon_title()
    bl_options = {'DEFAULT_CLOSED'} 

    def draw_header_preset(self, context):
        goal_ui = context.window_manager.ypui_sponsor
        if not goal_ui.expanded:
            layout = self.layout
            row = layout.row(align=True)
            row.operator('wm.url_open', text="Donate Us", icon='FUND').url = "https://github.com/sponsors/ucupumar"

        goal_ui.expanded = False

    def draw_item(self, layout, icon, label, url = '', scale_icon:float = 3.0, horizontal_mode:bool = True):
        if horizontal_mode:
            row = layout.row(align=True)
            row.alignment = 'LEFT'
            row.template_icon(icon_value = icon, scale = scale_icon)
            btn_url = row.operator('wm.url_open', text=label, emboss=False, )
            btn_url.url = url
            
        else:
            col = layout.column(align=True)
            col.template_icon(icon_value = icon, scale = scale_icon)
            col.operator('wm.url_open', text=label, emboss=False).url = url

    def draw_tier_members(self, goal_ui, layout, title:str, tier_index:int, per_column:int = 3, scale_icon:float = 3.0, horizontal_mode:bool = True):

        expand = goal_ui.expand_tiers[tier_index] if tier_index < len(goal_ui.expand_tiers) else False

        icon = 'TRIA_DOWN' if expand else 'TRIA_RIGHT'
        row = layout.row(align=True)
        rrow = row.row(align=True)
        filtered_items = list()

        for item in collaborators.sponsors.values():
            if item['tier'] != tier_index:
                continue
            filtered_items.append(item)


        text_object = f'{title.strip()} ({len(filtered_items)})'

        if is_bl_newer_than(2, 80):
            rrow.alignment = 'LEFT'
            rrow.scale_x = 0.95
            rrow.prop(goal_ui, 'expand_tiers', index=tier_index, emboss=False, text=text_object, icon=icon)
        else:
            rrow.prop(goal_ui, 'expand_tiers', index=tier_index, emboss=False, text='', icon=icon)
            rrow.label(text=text_object)

        if expand:
            
            if len(filtered_items) == 0:
                layout.label(text="No sponsors yet. Be the first one!")
            else:
                col = layout.column(align=True)
                missing_column = per_column - (len(filtered_items) % per_column)

                counter_member = 0
                for cl, item in enumerate(filtered_items):
                    counter_member += 1
                    if cl % per_column == 0:
                        row = col.row(align=True)
                        if horizontal_mode:
                            row.alignment = 'LEFT'
                            row.label( text=' ') # spacer

                    thumb = item['thumb']
                    if not thumb:
                        thumb = collaborators.default_pic

                    id = item["id"]
                    if item['one_time']:
                        id = "*" + id
                    self.draw_item(row, thumb, id, item["url"], scale_icon, horizontal_mode)

                if missing_column != per_column:
                    for i in range(missing_column):
                        self.draw_item(row, collaborators.default_pic, '', '', scale_icon, horizontal_mode)

    def draw(self, context):
        layout = self.layout
        goal = collaborators.sponsorship_goal
        goal_ui = context.window_manager.ypui_sponsor

        if goal and 'targetValue' in goal:
            layout.label(text="Ucupaint's goal : $" + str(goal['targetValue']) + "/month")
            target = goal['targetValue']
            percentage = goal['percentComplete']
            donation = target * percentage / 100
        
            goal_ui.progress = goal['percentComplete']
            layout.prop(goal_ui, 'progress', text=f"${donation}", slider=True)

        don_col = layout.column(align=True)
        don_col.scale_y = 1.5
        don_col.operator('wm.url_open', text="Donate Us", icon='FUND').url = "https://github.com/sponsors/ucupumar"
        
        if not goal_ui.initialized: # first time init
            goal_ui.initialized = True
            print("first time init, loading contributors...")
            load_contributors()

        if is_online():
            layout.separator()
            tiers:list = goal.get('tiers', [])
            if tiers:
                for tier in reversed(tiers):
                    idx = tiers.index(tier)

                    # self.draw_tier_members(goal_ui,layout, tier['name'], idx, 1, 1.0, True)
                    self.draw_tier_members(goal_ui,layout, tier['name'], idx, 3, 3.0, False)

            layout.separator()
            layout.label(text="* One-time sponsor")
        goal_ui.expanded = True

def load_preview(key:str, file_name:str):
    if key in previews_users:
        img = previews_users[key]
    else:
        img = previews_users.load(key, file_name, 'IMAGE', True)
    return img


def load_contributors():    

    reload_contributors = False
    path = get_addon_filepath()
    path_last_check = os.path.join(path, "last_check.txt") # to store last check time

    current_time = time.time()

    if os.path.exists(path_last_check):
        with open(path_last_check, "r", encoding="utf-8") as f:
            content_last_check = f.read().strip()
            
            # convert to float
            try:
                last_check = float(content_last_check)
            except:
                last_check = 0.0
            

            span_time = current_time - last_check
            # if last check more than a day ago, reload
            if span_time > 24 * 60 * 60:
                reload_contributors = True
            else:
                # format span in hours
                span_hours = span_time / 3600
                format_last_check = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(last_check))
                print(f"Last check was {span_hours:.2f} hours ago. Checked at {format_last_check}. Not reloading contributors.")
    else:
        reload_contributors = True       


    path_contributors = os.path.join(path, "contributors.csv")
    content = ""

    # read file if exists
    if os.path.exists(path_contributors):
        with open(path_contributors, "r", encoding="utf-8") as f:
            content = f.read()
    else:
        reload_contributors = True

    path_sponsors = os.path.join(path, "sponsors.csv")
    content_sponsors = ""

    if os.path.exists(path_sponsors):
        with open(path_sponsors, "r", encoding="utf-8") as f:
            content_sponsors = f.read()
    else:
        reload_contributors = True

    path_sponsorship_goal = os.path.join(path, "sponsorship-goal.json")
    content_sponsorship_goal = ""

    if os.path.exists(path_sponsorship_goal):
        with open(path_sponsorship_goal, "r", encoding="utf-8") as f:
            content_sponsorship_goal = f.read()
            collaborators.sponsorship_goal = json.loads(content_sponsorship_goal)
    else:
        reload_contributors = True

    if reload_contributors and is_online():

        data_url = "https://raw.githubusercontent.com/ucupumar/ucupaint-wiki/master/data/"
        try:
            print("Reloading contributors...")
            response = requests.get(data_url + "contributors.csv", verify=False, timeout=10)
            if response.status_code == 200:
                content = response.text
                print("Response:", content)

                with open(path_contributors, "w", encoding="utf-8") as f:
                    f.write(content)

            print("Reloading sponsors...")
            response = requests.get(data_url + "sponsors.csv", verify=False, timeout=10)
            if response.status_code == 200:
                content_sponsors = response.text
                print("Response:", content_sponsors)
                with open(path_sponsors, "w", encoding="utf-8") as f:
                    f.write(content_sponsors)

            response = requests.get(data_url + "sponsorship-goal.json", verify=False, timeout=10)
            if response.status_code == 200:
                content_sponsorship_goal = response.text
                print("Response:", content_sponsorship_goal)
                with open(path_sponsorship_goal, "w", encoding="utf-8") as f:
                    f.write(content_sponsorship_goal)
                collaborators.sponsorship_goal = json.loads(content_sponsorship_goal)

            current_time = time.time()
            with open(path_last_check, "w", encoding="utf-8") as f:
                f.write(str(current_time))

        except requests.exceptions.ReadTimeout:
            reload_contributors = False
    else:
        reload_contributors = False


    collaborators.contributors.clear()
    for line in content.strip().splitlines():
        parts = [p.strip() for p in line.split(',')]
        if len(parts) >= 3:
            contributor = {
                'id': parts[0],
                'url': parts[1],
                'image_url': parts[2],
                'thumb': None
            }
            collaborators.contributors[contributor['id']] = contributor

    folders = os.path.join(path, "icons", "contributors")
    if not os.path.exists(folders):
        os.makedirs(folders)

    collaborators.sponsors.clear()
    for line in content_sponsors.strip().splitlines():
        parts = [p.strip() for p in line.split(',')]
        if len(parts) >= 6:
            sponsor = {
                'id': parts[0],
                'url': parts[1],
                'image_url': parts[2],
                'one_time' : parts[5] == 'True',
                'tier': int(parts[6]),
                
                'thumb': None
            }
            collaborators.sponsors[sponsor['id']] = sponsor

    # Download contributor images
    links = [c['image_url']+"&s=108" for c in collaborators.contributors.values()]
    file_names = [f"{folders}{os.sep}{c['id']}.png" for c in collaborators.contributors.values()]
    ids = [c['id'] for c in collaborators.contributors.values()]

    # check images exist
    for file_name in file_names:
        if not os.path.exists(file_name):
            reload_contributors = True
            break

    # Download sponsor images
    links_sponsors = [c['image_url']+"&s=108" for c in collaborators.sponsors.values()]
    file_names_sponsors = [f"{folders}{os.sep}{c['id']}.png" for c in collaborators.sponsors.values()]
    ids_sponsors = [c['id'] for c in collaborators.sponsors.values()]

    # check images exist
    for file_name in file_names_sponsors:
        if not os.path.exists(file_name):
            reload_contributors = True
            break

    if reload_contributors:
        new_thread = threading.Thread(target=download_stream, args=(links,file_names,ids, collaborators.contributors))
        new_thread.start()

        new_thread_sponsors = threading.Thread(target=download_stream, args=(links_sponsors,file_names_sponsors,ids_sponsors, collaborators.sponsors))
        new_thread_sponsors.start()
    else:
        for idx, file_name in enumerate(file_names):
            k = ids[idx]
            if os.path.exists(file_name):
                img = load_preview(k, file_name)
                collaborators.contributors[k]['thumb'] = img.icon_id
                print("loaded contributor ", k, " = ", collaborators.contributors[k])
            else:
                print("file not found", file_name)

        for idx, file_name in enumerate(file_names_sponsors):
            k = ids_sponsors[idx]
            if os.path.exists(file_name):
                img = load_preview(k, file_name)
                collaborators.sponsors[k]['thumb'] = img.icon_id
                print("loaded sponsor ", k, " = ", collaborators.sponsors[k])
            else:
                print("file not found", file_name)

def download_stream(links:list[str], file_names:list[str], ids:list[str], dict, timeout:int = 10):
    for idx, file_name in enumerate(file_names):
        link = links[idx]
        print("Downloading", link, "to", file_name)
        with open(file_name, "wb") as f:
            try:
                response = requests.get(link, stream=True, timeout = timeout)
                total_length = response.headers.get('content-length')
                print("total size = "+total_length)
                if not total_length:
                    print('Error #1 while downloading', link, ':', "Empty Response.")
                    return
                
                dl = 0
                total_length = int(total_length)
                # TODO a way for calculating the chunk size
                for data in response.iter_content(chunk_size = 4096):

                    dl += len(data)
                    f.write(data)
            except Exception as e:
                print('Error #2 while downloading', link, ':', e)

        k = ids[idx]
        img = load_preview(k, file_name)
        dict[k]['thumb'] = img.icon_id
        print("loaded", k, " = ", dict[k])

classes = [
    VIEW3D_PT_YPaint_support_ui,
    YSponsorProp
]

class Collaborators:
    default_pic = None
    contributors = {}
    sponsors = {}
    sponsorship_goal = {}

def get_collaborators():
    return collaborators

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    global previews_users
    global collaborators

    collaborators = Collaborators()

    previews_users = bpy.utils.previews.new()

    blank_path = os.path.join(get_addon_filepath(), "icons", "blank.png")
    blank_img = load_preview('blank', blank_path)

    collaborators.default_pic = blank_img.icon_id
    collaborators.contributors = {}
    collaborators.sponsors = {}
    collaborators.sponsorship_goal = {}

    bpy.types.WindowManager.ypui_sponsor = PointerProperty(type=YSponsorProp)

    ui_sp = bpy.context.window_manager.ypui_sponsor
    ui_sp.initialized = False

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)

    del bpy.types.WindowManager.ypui_sponsor

    global previews_users

    bpy.utils.previews.remove(previews_users)
    previews_users = None

