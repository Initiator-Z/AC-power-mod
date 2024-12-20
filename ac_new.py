import argparse
import os
import shutil
import base64
from PIL import Image
import streamlit as st
from st_clickable_images import clickable_images

# ---------------------------- Constants & Config ---------------------------- #
CAR_BRANDS = [
    'Ferrari', 'Lamborghini', 'Porsche', 'BMW', 'Mercedes', 'Audi', 'McLaren',
    'Bugatti', 'Aston Martin', 'Jaguar', 'Koenigsegg', 'Pagani', 'Bentley',
    'Rolls Royce', 'Maserati', 'Alfa Romeo', 'Tesla', 'Honda', 'Toyota',
    'Nissan', 'Chevrolet', 'Ford', 'Dodge', 'Subaru', 'Mazda', 'Volkswagen',
    'Hyundai', 'Kia', 'Volvo', 'Renault', 'Peugeot', 'Citroen', 'Seat', 'Holden',
    'Skoda', 'Fiat', 'Suzuki', 'Genesis', 'Infiniti', 'Lexus', 'Acura', 'Lotus',
    'Buick', 'Cadillac', 'Chrysler', 'Jeep', 'Mini', 'Smart', 'Saab', 'Mitsubishi',
    'Isuzu', 'Lincoln', 'Ram', 'Geely', 'Great Wall', 'Tata', 'Mahindra'
]

st.set_page_config(page_title="🏎️ Car Power Modifier", layout="wide", initial_sidebar_state="expanded")

def get_screen_name(car_path):
    # Extract SCREEN_NAME from car.ini; strip comments after ';'.
    ini = os.path.join(car_path, 'data', 'car.ini')
    if os.path.exists(ini):
        with open(ini, 'r') as f:
            for line in f:
                if line.startswith('SCREEN_NAME='):
                    line = line.strip().split(';', 1)[0]
                    parts = line.split('=', 1)
                    if len(parts) > 1:
                        return parts[1].strip()
    return os.path.basename(car_path)

def extract_brand(folder, screen, brands):
    # Determine brand by checking folder and screen name.
    lf, ls = folder.lower(), screen.lower()
    for b in brands:
        lb = b.lower()
        if lb in lf or lb in ls:
            return b
    return 'Unknown'

def get_unique_brands(cars_path, brands):
    # Return sorted list of unique brands found.
    return sorted({extract_brand(c, get_screen_name(os.path.join(cars_path, c)), brands)
                   for c in os.listdir(cars_path) if os.path.isdir(os.path.join(cars_path, c))})

def get_cars(cars_path, brand, brands):
    # Return (folder, screen_name) for cars matching the selected brand.
    return [(c, get_screen_name(os.path.join(cars_path, c)))
            for c in os.listdir(cars_path)
            if os.path.isdir(os.path.join(cars_path, c))
            and (brand == 'All Brands' or extract_brand(c, get_screen_name(os.path.join(cars_path, c)), brands) == brand)]

def get_brand_logo_path(cars_path, brand):
    # Find and return path to brand logo (badge.png).
    for car in os.listdir(cars_path):
        cp = os.path.join(cars_path, car)
        if os.path.isdir(cp):
            sc = get_screen_name(cp)
            if extract_brand(car, sc, CAR_BRANDS) == brand:
                bp = os.path.join(cp, 'ui', 'badge.png')
                if os.path.exists(bp):
                    return bp
    return None

def backup_file(original_path):
    # Backup original LUT file if not already backed up.
    bp = original_path + '.bak'
    if not os.path.exists(bp):
        shutil.copy(original_path, bp)
        st.info(f'✅ Backup created at {bp}')
    else:
        st.info(f'ℹ️ Backup already exists at {bp}')

def validate_lut(fp):
    # Validate LUT format: 'rpm|value' and value is numeric.
    try:
        with open(fp, 'r') as f:
            for i, line in enumerate(f, 1):
                l = ''.join(line.split())
                if not l:
                    continue
                parts = l.split('|')
                if len(parts) != 2 or not parts[1].replace('.', '', 1).isdigit():
                    st.error(f'❌ Invalid line {i}: "{line.strip()}"')
                    return False
        return True
    except Exception as e:
        st.error(f'❌ LUT validation error: {e}')
        return False

def load_doc(p):
    with open(p, 'r') as f:
        return f.readlines()

def read_rpm(lines):
    # Parse torque values only if rpm >= 0.
    vals = []
    for line in lines:
        l = line.strip()
        if l:
            parts = l.split('|')
            if len(parts) == 2:
                try:
                    rpm = float(parts[0])
                    val = float(parts[1])
                    if rpm >= 0:
                        vals.append(val)
                except:
                    pass
    return vals

def get_modifier(cur, tgt):
    # Return multiplier (target / current).
    if cur == 0:
        st.error("❌ Initial value cannot be zero.")
        return 1
    return tgt / cur

def get_rpm(vals, m):
    # Apply multiplier to all values.
    return [round(x * m, 2) for x in vals]

def final_power(original, modified):
    # Create final LUT lines with modified values.
    res, idx = [], 0
    for line in original:
        l = line.strip()
        if not l:
            res.append(line)
            continue
        parts = l.split('|')
        if len(parts) == 2 and idx < len(modified):
            rpm = parts[0]
            res.append(f'{rpm}|{modified[idx]}\n')
            idx += 1
        else:
            res.append(line)
    return res

def write_doc(path, current, target):
    # Write updated LUT values to file.
    try:
        rpm_file = load_doc(path)
        rpm_vals = read_rpm(rpm_file)
        m = get_modifier(current, target)
        if m == 1:
            st.warning('⚠️ No changes applied (multiplier=1).')
            return
        final = final_power(rpm_file, get_rpm(rpm_vals, m))
        with open(path, 'w') as f:
            f.writelines(final)
        st.success('✅ Car values modified successfully!')
    except Exception as e:
        st.error(f'❌ Modification error: {e}')

def get_first_folder(p):
    # Get first subfolder without '.'.
    return next((f for f in os.listdir(p) if os.path.isdir(os.path.join(p, f))), None) if os.path.exists(p) else None

def get_max_value_from_lut(fp):
    # Get max torque value from LUT ignoring negative RPM.
    mv = 0.0
    if os.path.exists(fp):
        with open(fp, 'r') as f:
            for line in f:
                parts = line.strip().split('|')
                if len(parts) == 2:
                    try:
                        rpm = float(parts[0])
                        val = float(parts[1])
                        if rpm >= 0 and val > mv:
                            mv = val
                    except:
                        pass
    return mv

def get_power_lut_filename(dp):
    # Read engine.ini [HEADER] for POWER_CURVE filename.
    ei = os.path.join(dp, 'engine.ini')
    if os.path.exists(ei):
        with open(ei, 'r') as f:
            hdr = False
            for line in f:
                s = line.strip()
                if s.upper() == '[HEADER]':
                    hdr = True
                    continue
                if hdr and s.startswith('POWER_CURVE='):
                    filename = s.split('=',1)[1].split(';',1)[0].strip()
                    if filename:
                        return filename
    return 'power.lut'

def detect_turbo_and_max_boost(dp):
    # Check if [TURBO_0] exists and return MAX_BOOST if found.
    ei = os.path.join(dp, 'engine.ini')
    if os.path.exists(ei):
        with open(ei, 'r') as f:
            turbo = False
            for line in f:
                s = line.strip()
                if s.upper() == '[TURBO_0]':
                    turbo = True
                    continue
                if turbo:
                    if s.startswith('[') and s.endswith(']'):
                        break
                    if s.startswith('MAX_BOOST='):
                        try:
                            return float(s.split('=',1)[1].split(';',1)[0].strip())
                        except:
                            return None
    return None

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--path', type=str, default='D:/Steam/steamapps/common/assettocorsa/content/cars/', help='AC cars path.')
    parser.add_argument('--initial_power', type=float, default=0.0, help='Initial power (HP).')
    parser.add_argument('--target_power', type=float, default=0.0, help='Target power (HP).')
    args, _ = parser.parse_known_args()

    # Check if path exists
    if not os.path.exists(args.path):
        st.sidebar.error(f"❌ Path does not exist: {args.path}")
        return

    # Get brand list
    brands = get_unique_brands(args.path, CAR_BRANDS)
    if not brands:
        st.sidebar.error("❌ No car brands found.")
        return

    # Header
    st.header("**Modify Car Power/Torque**")

    # ------------------- Brand Selection in Sidebar ------------------- #
    st.sidebar.header('Select a Brand')
    with st.sidebar.container():
        images, titles = [], []
        for b in brands:
            bp = get_brand_logo_path(args.path, b)
            if bp and os.path.exists(bp):
                with open(bp, "rb") as imgf:
                    encoded = base64.b64encode(imgf.read()).decode()
                    images.append(f"data:image/png;base64,{encoded}")
                    titles.append(b)

        clicked = clickable_images(
            images,
            titles=titles,
            div_style={"display": "flex", "justify-content": "center", "flex-wrap": "wrap"},
            img_style={"margin": "5px", "height": "50px"},
        )

        if clicked > -1:
            st.session_state.selected_brand = titles[clicked]
        else:
            st.info("No brand selected")

    # ------------------- Car Selection ------------------- #
    col1, col2 = st.columns(2)
    with col1:
        sel_brand = st.session_state.get('selected_brand', 'All Brands')
        cars = get_cars(args.path, sel_brand, CAR_BRANDS)
        if not cars and sel_brand != 'All Brands':
            st.warning(f"⚠️ No cars for brand: {sel_brand}")
            selected_car_folder = None
        else:
            keyword = st.text_input('🔍 Search Cars by Folder Name:', placeholder='Enter keywords...', help='Filter cars by folder name.').lower().strip()
            cars_display = [(f, s) for (f, s) in cars if keyword in f.lower()] if keyword else cars

            if not cars_display and keyword:
                st.warning(f"⚠️ No cars match: '{keyword}'")

            if cars_display:
                # Handle duplicate screen names
                sn_counts = {}
                for (fd, scn) in cars_display:
                    sn_counts[scn] = sn_counts.get(scn,0)+1

                display_options = []
                name_map = {}
                occ = {}
                for (fd, scn) in cars_display:
                    if sn_counts[scn] > 1:
                        occ[scn] = occ.get(scn,0)+1
                        dscn = f"{scn} (#{occ[scn]})"
                    else:
                        dscn = scn
                    display_options.append(dscn)
                    name_map[dscn] = fd

                selected_car_option = st.selectbox('Select a Car:', display_options)
                selected_car_folder = name_map[selected_car_option]
                st.write(f"**Selected Car:** `{selected_car_folder}`")
                args.carname = selected_car_folder
            else:
                selected_car_folder = None

    with col2:
        st.empty()

    # ------------------- Power/Torque Modification ------------------- #
    if selected_car_folder:
        cdp = os.path.join(args.path, args.carname, 'data')
        lut_file = get_power_lut_filename(cdp)
        lut_path = os.path.join(cdp, lut_file)

        ptype = st.radio("Select Value Type to Modify:", ('Horsepower', 'Torque'))

        if ptype == 'Torque':
            if os.path.exists(lut_path):
                mt = get_max_value_from_lut(lut_path)
                mb = detect_turbo_and_max_boost(cdp)
                adjusted = mt*(1.0+mb) if mb else mt
                final_t = adjusted
                init_val = st.number_input('Initial Torque:', 0.0, None, float(adjusted), 1.0, help='Max torque (adjusted if turbo).')
            else:
                mb = detect_turbo_and_max_boost(cdp)
                dt = 0.0
                if mb: dt *= (1.0+mb)
                final_t = dt
                init_val = st.number_input('Initial Torque:', 0.0, None, dt, 1.0, help='Estimated max torque.')
            tgt_val = st.number_input('Target Torque:', 0.0, None, final_t, 1.0, help='Desired max torque.')
        else:
            init_val = st.number_input('Initial Power (HP):', 0.0, None, args.initial_power, 1.0, help='Current HP.')
            tgt_val = st.number_input('Target Power (HP):', 0.0, None, args.target_power, 1.0, help='Desired HP.')

        st.markdown("---")
        # ------------------- Skin Preview ------------------- #
        skins_path = os.path.join(args.path, args.carname, 'skins')
        first_skin = get_first_folder(skins_path)
        if first_skin:
            skin_folders = [fd for fd in os.listdir(skins_path) if os.path.isdir(os.path.join(skins_path, fd))]
            sel_skin = st.selectbox('Select a Skin for Preview:', skin_folders, help='Preview selected skin.')
            pv = os.path.join(skins_path, sel_skin, 'preview.jpg')
            if os.path.exists(pv):
                st.image(Image.open(pv), caption=f'{sel_skin} Preview', use_container_width=True)
            else:
                st.warning('⚠️ Skin preview not found.')
        else:
            st.warning('⚠️ No skins available.')

        st.markdown("---")
        # ------------------- Modification Action ------------------- #
        if st.button(f'🚀 Modify Car {ptype}'):
            if os.path.exists(lut_path):
                if validate_lut(lut_path):
                    with st.spinner('🔄 Backing up original LUT...'):
                        backup_file(lut_path)
                    with st.spinner(f'⚙️ Modifying car {ptype.lower()}...'):
                        write_doc(lut_path, init_val, tgt_val)
                else:
                    st.error('❌ Invalid LUT format.')
            else:
                st.error('❌ Car data packed or LUT file not found.')

        st.markdown("---")

if __name__ == '__main__':
    main()
