"""TTIF 共通のデザイン(色・角丸・影)。全画面でここの値を使うと見た目が揃う。"""
import flet as ft

PINK = "#F7C6D9"
PINK_DEEP = "#E58BAF"
LAVENDER = "#DCCFF5"
LAVENDER_DEEP = "#9B7FD4"
WHITE = "#FFFFFF"
GRAY_BG = "#F7F5FA"
GRAY_LINE = "#E8E4EE"
TEXT = "#4A4458"
TEXT_SUB = "#8E879C"

RADIUS = 20
FONT_FAMILY = "Yu Gothic UI"


def app_theme() -> ft.Theme:
    return ft.Theme(color_scheme_seed=LAVENDER_DEEP, font_family=FONT_FAMILY)


def card(content: ft.Control, padding: int = 20) -> ft.Container:
    """白くて角の丸いカード。画面の各ブロックを包むのに使う。"""
    return ft.Container(
        content=content,
        bgcolor=WHITE,
        border_radius=RADIUS,
        padding=padding,
        shadow=ft.BoxShadow(blur_radius=18, color=ft.Colors.with_opacity(0.08, ft.Colors.BLACK), offset=ft.Offset(0, 4)),
    )


def input_border() -> ft.OutlineInputBorder:
    """入力欄(TextField / Dropdown)の角丸の枠線。"""
    return ft.OutlineInputBorder(border_radius=14, side=ft.BorderSide(1, GRAY_LINE))
