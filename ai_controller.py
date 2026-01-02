import cv2
import mediapipe as mp
from mediapipe.tasks.python.vision.core import (
    image_processing_options as image_processing_options_module,
)
import time
import math
import traceback

MODEL_PATH = "hand_landmarker.task"

# --- CẤU HÌNH ĐỘ NHẠY ---
VELOCITY_THRESHOLD = 0.015
HIGH_VELOCITY_TRIGGER = 0.06
GUARD_DISTANCE = 0.25
MIN_FOLDED_FINGERS = 3
PUNCH_COOLDOWN = 0.35


def ai_process(command_queue, frame_queue, stop_event):
    BaseOptions = mp.tasks.BaseOptions
    HandLandmarker = mp.tasks.vision.HandLandmarker
    HandLandmarkerOptions = mp.tasks.vision.HandLandmarkerOptions
    VisionRunningMode = mp.tasks.vision.RunningMode
    Image = mp.Image
    ImageProcessingOptions = image_processing_options_module.ImageProcessingOptions

    # State variables
    prev_cords = {}
    last_punch_time = 0
    current_fps = 0
    frame_count = 0
    start_time = time.time()

    debug_info = {
        "action": "IDLE",
        "hand_state": "OPEN",
        "handedness": "-",
        "last_velocity": 0.0,
    }

    def result_callback(result, output_image, timestamp_ms):
        nonlocal last_punch_time, debug_info, prev_cords

        if stop_event.is_set():
            return

        command = []
        left_hand_wrist = None
        right_hand_wrist = None

        debug_info["hand_state"] = "OPEN"
        debug_info["action"] = "IDLE"

        if result.hand_landmarks:
            for i, hand_landmarks in enumerate(result.hand_landmarks):
                try:
                    # 1. Xác định tay
                    handedness = "Unknown"
                    if result.handedness and len(result.handedness) > i:
                        cat = result.handedness[i][0].category_name
                        handedness = "Left" if cat == "Right" else "Right"

                    wrist = hand_landmarks[0]
                    if handedness == "Left":
                        left_hand_wrist = wrist
                    if handedness == "Right":
                        right_hand_wrist = wrist

                    # 2. Tính vận tốc (Quan trọng)
                    prev = prev_cords.get(handedness, (wrist.x, wrist.y))
                    dx = wrist.x - prev[0]
                    dy = wrist.y - prev[1]
                    velocity = math.sqrt(dx**2 + dy**2)
                    prev_cords[handedness] = (wrist.x, wrist.y)

                    # Cập nhật debug để hiển thị lên màn hình
                    if velocity > 0.005:  # Chỉ hiện nếu có chuyển động
                        debug_info["last_velocity"] = velocity

                    # 3. Kiểm tra nắm tay (Fist)
                    tips = [8, 12, 16, 20]
                    mcps = [5, 9, 13, 17]
                    folded = 0
                    for t, m in zip(tips, mcps):
                        dist_t = math.hypot(
                            hand_landmarks[t].x - wrist.x, hand_landmarks[t].y - wrist.y
                        )
                        dist_m = math.hypot(
                            hand_landmarks[m].x - wrist.x, hand_landmarks[m].y - wrist.y
                        )
                        if dist_t < dist_m:
                            folded += 1

                    is_fist = folded >= MIN_FOLDED_FINGERS
                    if is_fist:
                        debug_info["hand_state"] = "FIST"

                    # --- DEBUG LOGGING (Quan trọng: Xem Terminal để biết tốc độ thực tế) ---
                    # Nếu bạn thấy V thấp hơn 0.015 khi đấm, hãy giảm VELOCITY_THRESHOLD thêm nữa
                    if velocity > 0.01:
                        print(
                            f"[{handedness}] V={velocity:.3f} | Fist={is_fist} | Folded={folded}"
                        )

                    # 4. Logic Đấm (Đã cải tiến)
                    current_time = time.time()
                    if current_time - last_punch_time > PUNCH_COOLDOWN:

                        # ĐIỀU KIỆN ĐẤM:
                        # Hoặc là (Nắm tay VÀ Tốc độ > Ngưỡng thấp)
                        # Hoặc là (Tốc độ > Ngưỡng cao - Bất chấp nắm tay hay không - Chống nhòe hình)
                        trigger_punch = (is_fist and velocity > VELOCITY_THRESHOLD) or (
                            velocity > HIGH_VELOCITY_TRIGGER
                        )

                        if trigger_punch:
                            cmd = None

                            # Phân loại hướng đấm
                            # Vùng trung tâm (Straight) rộng hơn một chút (0.35 - 0.65)
                            if 0.35 < wrist.x < 0.65:
                                cmd = "PUNCH_S"
                            elif abs(dx) > abs(dy) * 1.2:  # Hook
                                if (handedness == "Right" and dx > 0) or (
                                    handedness == "Left" and dx < 0
                                ):
                                    cmd = (
                                        "PUNCH_R"
                                        if handedness == "Right"
                                        else "PUNCH_L"
                                    )
                                else:
                                    cmd = (
                                        "PUNCH_L"
                                        if handedness == "Right"
                                        else "PUNCH_R"
                                    )
                            else:
                                cmd = "PUNCH_R" if handedness == "Right" else "PUNCH_L"

                            if cmd:
                                command.append(cmd)
                                last_punch_time = current_time
                                debug_info["action"] = cmd
                                debug_info["handedness"] = handedness
                                print(f"===> TRIGGER: {cmd} (V={velocity:.3f})")

                except Exception as e:
                    pass

            # 5. Logic Phòng thủ
            if left_hand_wrist and right_hand_wrist:
                dist = math.hypot(
                    left_hand_wrist.x - right_hand_wrist.x,
                    left_hand_wrist.y - right_hand_wrist.y,
                )
                if dist < GUARD_DISTANCE:
                    command.append("DEFEND_ON")
                    debug_info["action"] = "GUARD"
                else:
                    command.append("DEFEND_OFF")
            else:
                command.append("DEFEND_OFF")

            # Gửi lệnh
            final_cmd = None
            for c in command:
                if "PUNCH" in c:
                    final_cmd = c
                    break
            if not final_cmd and "DEFEND_ON" in command:
                final_cmd = "DEFEND_ON"
            if not final_cmd and "DEFEND_OFF" in command:
                final_cmd = "DEFEND_OFF"

            if final_cmd and not command_queue.full():
                command_queue.put_nowait(final_cmd)

    # --- SETUP & LOOP ---
    try:
        options = HandLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=MODEL_PATH),
            running_mode=VisionRunningMode.LIVE_STREAM,
            result_callback=result_callback,
            num_hands=2,
            min_hand_detection_confidence=0.5,
            min_hand_presence_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        landmarker = HandLandmarker.create_from_options(options)
    except Exception as e:
        print(f"AI Init Error: {e}")
        return

    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    print("AI Ready.")

    while not stop_event.is_set():
        ret, frame = cap.read()
        if not ret:
            break

        frame = cv2.flip(frame, 1)
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        timestamp_ms = int(time.time() * 1000)
        mp_image = Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
        landmarker.detect_async(
            mp_image, timestamp_ms, ImageProcessingOptions(region_of_interest=None)
        )

        # FPS Calc
        frame_count += 1
        if time.time() - start_time > 1:
            current_fps = frame_count / (time.time() - start_time)
            frame_count = 0
            start_time = time.time()

        # Draw UI
        overlay = frame.copy()
        cv2.rectangle(
            overlay, (0, 0), (220, 130), (0, 0, 0), -1
        )  # Kéo dài box để hiện velocity
        frame = cv2.addWeighted(overlay, 0.5, frame, 0.5, 0)

        cv2.putText(
            frame,
            f"FPS: {int(current_fps)}",
            (10, 25),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 255, 0),
            2,
        )

        color_state = (
            (0, 255, 255) if debug_info["hand_state"] == "FIST" else (0, 255, 0)
        )
        cv2.putText(
            frame,
            f"Hand: {debug_info['hand_state']}",
            (10, 55),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            color_state,
            2,
        )

        # Hiện Velocity lên màn hình để dễ debug
        cv2.putText(
            frame,
            f"Vel : {debug_info['last_velocity']:.3f}",
            (10, 85),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (255, 255, 0),
            2,
        )

        color_act = (
            (0, 0, 255)
            if "PUNCH" in debug_info["action"]
            else ((255, 0, 0) if "GUARD" in debug_info["action"] else (200, 200, 200))
        )
        cv2.putText(
            frame,
            f"Act : {debug_info['action']}",
            (10, 115),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            color_act,
            2,
        )

        try:
            small_frame = cv2.resize(frame, (320, 240))
            small_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)
            if frame_queue.full():
                try:
                    frame_queue.get_nowait()
                except:
                    pass
            frame_queue.put_nowait(small_frame)
        except:
            pass

    cap.release()
