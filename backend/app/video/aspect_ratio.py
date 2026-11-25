import logging
from typing import Dict, Tuple

logger = logging.getLogger("clipforge.video.aspect_ratio")

TARGET_DIMENSIONS: Dict[str, Tuple[int, int]] = {
    "9:16": (1080, 1920),
    "1:1": (1080, 1080),
    "4:5": (1080, 1350),
    "16:9": (1920, 1080),
}

class AspectRatioProcessor:
    @staticmethod
    def get_target_dimensions(aspect_ratio: str) -> Tuple[int, int]:
        return TARGET_DIMENSIONS.get(aspect_ratio, (1080, 1920))

    @staticmethod
    def build_smart_crop_filtergraph(
        crop_w: int,
        crop_h: int,
        crop_x: int,
        crop_y: int,
        aspect_ratio: str = "9:16",
    ) -> str:
        """
        Build an FFmpeg filtergraph for a specific subject-centered crop window.
        """
        tw, th = AspectRatioProcessor.get_target_dimensions(aspect_ratio)
        return f"crop={crop_w}:{crop_h}:{crop_x}:{crop_y},scale={tw}:{th}:flags=bicubic"

    @staticmethod
    def build_trajectory_filtergraph(
        crop_w: int,
        crop_h: int,
        trajectory: list, # List[CropCoordinate] or dicts
        aspect_ratio: str = "9:16",
    ) -> str:
        """
        Build an FFmpeg filtergraph with dynamic time-varying crop trajectory.
        Uses piecewise linear interpolation for smooth camera motion.
        """
        tw, th = AspectRatioProcessor.get_target_dimensions(aspect_ratio)
        if not trajectory:
            return AspectRatioProcessor.build_filtergraph(aspect_ratio, mode="center_crop")

        if len(trajectory) == 1:
            c = trajectory[0]
            px = getattr(c, "pixel_x", 0) if hasattr(c, "pixel_x") else c.get("pixel_x", 0)
            py = getattr(c, "pixel_y", 0) if hasattr(c, "pixel_y") else c.get("pixel_y", 0)
            return AspectRatioProcessor.build_smart_crop_filtergraph(crop_w, crop_h, px, py, aspect_ratio)

        # Downsample trajectory if very dense (e.g. take every 2nd or 3rd keyframe if > 30 points to keep ffmpeg expression clean)
        points = trajectory
        if len(points) > 30:
            step = max(1, len(points) // 25)
            sampled = [points[i] for i in range(0, len(points), step)]
            if points[-1] not in sampled:
                sampled.append(points[-1])
            points = sampled

        # Build nested if expression for x(t) and y(t)
        # if(lt(t, t1), x0 + (x1-x0)*(t-t0)/(t1-t0), if(lt(t, t2), ...))
        def get_val(item, attr):
            return getattr(item, attr) if hasattr(item, attr) else item.get(attr, 0)

        t_last = get_val(points[-1], "timestamp_seconds")
        x_last = get_val(points[-1], "pixel_x")
        y_last = get_val(points[-1], "pixel_y")

        expr_x = f"{x_last}"
        expr_y = f"{y_last}"

        for i in range(len(points) - 2, -1, -1):
            p0 = points[i]
            p1 = points[i + 1]
            t0 = get_val(p0, "timestamp_seconds")
            t1 = get_val(p1, "timestamp_seconds")
            x0 = get_val(p0, "pixel_x")
            x1 = get_val(p1, "pixel_x")
            y0 = get_val(p0, "pixel_y")
            y1 = get_val(p1, "pixel_y")

            dt = max(0.01, t1 - t0)
            interp_x = f"({x0}+({x1}-{x0})*(t-{t0:.3f})/{dt:.3f})"
            interp_y = f"({y0}+({y1}-{y0})*(t-{t0:.3f})/{dt:.3f})"

            expr_x = f"if(lt(t,{t1:.3f}),{interp_x},{expr_x})"
            expr_y = f"if(lt(t,{t1:.3f}),{interp_y},{expr_y})"

        return f"crop={crop_w}:{crop_h}:'{expr_x}':'{expr_y}',scale={tw}:{th}:flags=bicubic"

    @staticmethod
    def build_filtergraph(
        aspect_ratio: str = "9:16",
        mode: str = "center_crop",
        blur_strength: int = 25
    ) -> str:
        """
        Build an FFmpeg video filter string for reframing.
        Modes:
          - center_crop: zooms and crops to fill target aspect ratio
          - fit_pad: keeps full content with black letterbox / pillarbox padding
          - blur_background: blurred, scaled background with centered foreground
        """
        tw, th = AspectRatioProcessor.get_target_dimensions(aspect_ratio)
        target_aspect = tw / th

        if mode == "fit_pad":
            return (
                f"scale={tw}:{th}:force_original_aspect_ratio=decrease,"
                f"pad={tw}:{th}:(ow-iw)/2:(oh-ih)/2:color=black"
            )

        elif mode == "blur_background":
            # Two-pass filtergraph with split, blurred background layer and overlaid sharp foreground
            return (
                f"split=2[bg_in][fg_in];"
                f"[bg_in]scale={tw}:{th}:force_original_aspect_ratio=increase,crop={tw}:{th},boxblur={blur_strength}:5[bg];"
                f"[fg_in]scale={tw}:{th}:force_original_aspect_ratio=decrease[fg];"
                f"[bg][fg]overlay=(W-w)/2:(H-h)/2"
            )

        else: # center_crop (default)
            # Crop to aspect ratio then scale
            return (
                f"crop='if(gte(a,{target_aspect:.6f}),ih*{target_aspect:.6f},iw)':"
                f"'if(gte(a,{target_aspect:.6f}),ih,iw/{target_aspect:.6f})',"
                f"scale={tw}:{th}:flags=bicubic"
            )
