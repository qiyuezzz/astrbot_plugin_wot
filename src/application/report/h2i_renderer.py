from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from astrbot.api import logger
from astrbot.core import html_renderer
from data.plugins.astrbot_plugin_wot.src.settings.constants import is_h2i_enabled

if TYPE_CHECKING:
    from playwright.async_api import Browser, Playwright

# Chromium 启动参数
CHROMIUM_LAUNCH_ARGS = [
    "--no-sandbox",
    "--disable-setuid-sandbox",
    "--disable-gpu",
    "--disable-dev-shm-usage",
]


async def _install_chromium() -> bool:
    """安装 Chromium（使用 npmmirror 镜像加速）。"""
    try:
        logger.info("H2I: 正在下载 Chromium 浏览器，请耐心等待...")
        proc = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "playwright",
            "install",
            "chromium",
            env={
                **os.environ,
                "PLAYWRIGHT_DOWNLOAD_HOST": "https://npmmirror.com/mirrors/playwright",
            },
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode == 0:
            logger.info("H2I: Chromium 浏览器下载完成，本地渲染已就绪")
            return True
        else:
            error_msg = stderr.decode("utf-8", errors="replace")
            logger.error(f"H2I: Chromium 下载失败: {error_msg}")
            return False
    except Exception as e:
        logger.error(f"H2I: 下载 Chromium 时发生错误: {e}")
        return False


class H2IRenderer:
    """HTML 转图片渲染器，自动安装并使用 Playwright Chromium，失败时降级到 T2I 远程服务。"""

    def __init__(self) -> None:
        self._browser: Browser | None = None
        self._playwright: Playwright | None = None
        self._initialized: bool = False
        self._init_lock: asyncio.Lock = asyncio.Lock()
        self._h2i_available: bool = False

    async def _ensure_browser(self) -> bool:
        """确保浏览器实例已就绪，返回是否可用。"""
        if self._initialized:
            return self._h2i_available

        async with self._init_lock:
            if self._initialized:
                return self._h2i_available

            logger.info("H2I: 正在初始化本地渲染引擎...")
            try:
                from playwright.async_api import async_playwright

                self._playwright = await async_playwright().start()
                self._browser = await self._playwright.chromium.launch(
                    args=CHROMIUM_LAUNCH_ARGS,
                )
                self._initialized = True
                self._h2i_available = True
                logger.info("H2I: 本地渲染引擎已就绪")
                return True
            except ImportError:
                logger.warning("H2I: playwright 未安装，将使用 T2I 远程服务")
                logger.info("H2I: 如需本地渲染，请运行: pip install playwright")
                self._initialized = True
                self._h2i_available = False
                return False
            except Exception as e:
                if "Executable doesn't exist" in str(e):
                    logger.info("H2I: 首次启用本地渲染，正在下载 Chromium...")
                    if await _install_chromium():
                        try:
                            if self._playwright is None:
                                self._playwright = await async_playwright().start()
                            self._browser = await self._playwright.chromium.launch(
                                args=CHROMIUM_LAUNCH_ARGS,
                            )
                            self._initialized = True
                            self._h2i_available = True
                            logger.info("H2I: 本地渲染引擎已就绪")
                            return True
                        except Exception as e2:
                            logger.warning(f"H2I: 浏览器启动失败: {e2}")
                    else:
                        logger.warning("H2I: Chromium 下载失败，将使用 T2I 远程服务")
                else:
                    logger.warning(f"H2I: 启动浏览器失败: {e}")

                self._initialized = True
                self._h2i_available = False
                return False

    async def render_report(
        self,
        send_id: str,
        html_output: str,
        report_dir: Path,
        options: dict | None = None,
    ) -> str:
        """渲染报表 HTML 为图片。"""
        self._clear_previous_artifacts(report_dir, send_id)
        h2i_enabled = is_h2i_enabled()
        logger.info(f"H2I: is_h2i_enabled={h2i_enabled}")
        if h2i_enabled and await self._ensure_browser():
            try:
                return await self._render_with_playwright(
                    html_output, report_dir, send_id, options
                )
            except Exception as e:
                logger.warning(f"H2I 本地渲染失败，降级到 T2I: {e}")

        return await self._render_with_t2i(html_output, report_dir, send_id, options)

    def _clear_previous_artifacts(self, report_dir: Path, send_id: str) -> None:
        """清理同一用户上次渲染遗留的产物，避免误读旧文件。"""
        for suffix in ("jpg", "url"):
            artifact_path = report_dir / f"{send_id}.{suffix}"
            try:
                artifact_path.unlink(missing_ok=True)
            except OSError as exc:
                logger.warning(f"H2I: 清理旧产物失败 {artifact_path}: {exc}")

    async def _render_with_playwright(
        self,
        html_output: str,
        report_dir: Path,
        send_id: str,
        options: dict | None,
    ) -> str:
        """使用 Playwright 渲染 HTML 为图片。"""
        from playwright.async_api import Error as PlaywrightError

        if self._browser is None:
            raise RuntimeError("浏览器未初始化")

        width = options.get("width", 2560) if options else 2560
        height = options.get("height", 2560) if options else 2560
        device_scale_factor = (
            options.get("device_scale_factor", 1.0) if options else 1.0
        )
        full_page = options.get("full_page", True) if options else True
        jpeg_quality = options.get("quality", 80) if options else 80

        page = await self._browser.new_page()
        try:
            await page.set_viewport_size({"width": width, "height": height})
            await page.evaluate(
                f"() => {{ window.devicePixelRatio = {device_scale_factor}; }}"
            )
            await page.set_content(html_output, wait_until="networkidle", timeout=30000)
            await page.evaluate("() => document.fonts.ready")
            await asyncio.sleep(0.5)

            screenshot_bytes = await page.screenshot(
                full_page=full_page,
                type="jpeg",
                quality=jpeg_quality,
            )

            image_path = report_dir / f"{send_id}.jpg"
            image_path.write_bytes(screenshot_bytes)
            logger.info(f"H2I: 图片已保存到 {image_path}")

            return f"file://{image_path.resolve()}"

        except PlaywrightError as e:
            raise RuntimeError(f"Playwright 渲染失败: {e}") from e
        finally:
            await page.close()

    async def _render_with_t2i(
        self,
        html_output: str,
        report_dir: Path,
        send_id: str,
        options: dict | None,
    ) -> str:
        """使用 AstrBot T2I 远程服务渲染图片。"""
        default_options = {
            "full_page": True,
            "type": "jpeg",
            "quality": 100,
            "width": 2560,
            "height": 2560,
            "device_scale_factor": 1,
        }
        if options:
            default_options = {**default_options, **options}

        image_url = await html_renderer.render_custom_template(
            html_output, {}, return_url=True, options=default_options
        )

        logger.info(f"T2I: 生成的图片 URL: {image_url}")

        url_file_path = report_dir / f"{send_id}.url"
        with open(url_file_path, "w", encoding="utf-8") as f:
            json.dump({"url": image_url}, f)

        logger.info(f"T2I: 图片 URL 已保存: {url_file_path}")
        return image_url

    async def close(self) -> None:
        """关闭浏览器实例。"""
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        self._initialized = False
        self._h2i_available = False
        self._browser = None
        self._playwright = None
        logger.info("H2I: 浏览器已关闭")
