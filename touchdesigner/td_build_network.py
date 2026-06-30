# pyright: reportUndefinedVariable=false
"""
TouchDesigner network installer for the birthday submission system.

Paste this file into a Text DAT named `build_net`, then run:

op("project1/build_net").module.installBirthdayTouchDesigner()

The installer is idempotent: it can be run multiple times and will only create
missing operators or refresh helper scripts.
"""

from pathlib import Path
import json
from urllib.request import urlopen

MAX_PREVIEW_CARDS = 20
CANVAS_WIDTH = 1920
CANVAS_HEIGHT = 1080
ENTRY_WIDTH = 1600
ENTRY_HEIGHT = 900
OSC_IN_PORT = 9001
OSC_SUBMISSION_ADDRESS = "/birthday/submission"
PROJECT_ROOT = Path(r"C:\Users\PC\Documents\gilang-stuff\PROJ_TouchDesigner-stuff\HBD-SuRyA-PaLoH")
SPAWNER_FRAMEWORK_FILE = PROJECT_ROOT / "touchdesigner" / "td_spawner_framework.py"


def installBirthdayTouchDesigner():
    project = op("/project1")
    controller = buildController(project)
    template = buildSubmissionTemplate(project)
    ensureGeneratedPoolCopies(controller, template)
    preview = buildPreviewNetwork(project)
    buildFavoriteWindow(project)
    buildPreviewAutoWire(project)
    buildControlPanel(project)
    startBirthdayRuntime()
    forceCookPreview()

    print("Birthday TouchDesigner network is ready.")
    print("Controller: {}".format(controller.path))
    print("Template:   {}".format(template.path))
    print("Preview:    {}".format(preview.path))
    return controller


def buildBirthdayNetwork():
    """Backward-compatible alias."""
    return installBirthdayTouchDesigner()


def clearGeneratedPool(controller):
    pool = controller.op("spawner_pool") if controller else None
    if not pool:
        return

    removed = 0
    for child in list(pool.children):
        if child.name.startswith("submission_"):
            try:
                child.destroy()
                removed += 1
            except Exception:
                pass

    if removed:
        print("Cleared {} generated pool COMPs so template can be recopied.".format(removed))


def ensureGeneratedPoolCopies(controller, template):
    pool = controller.op("spawner_pool") if controller else None
    if not pool or not template:
        return 0

    created = 0
    for index in range(1, MAX_PREVIEW_CARDS + 1):
        name = "submission_{:02d}".format(index)
        if pool.op(name):
            continue
        try:
            copied = pool.copy(template, name=name)
            copied.nodeX = (index - 1) * 160
            copied.nodeY = -260
            created += 1
        except Exception as err:
            print("Failed creating {}: {}".format(name, err))

    if created:
        print("Created {} missing pool COMPs.".format(created))
    return created


def rebuildBirthdayPool():
    controller = op("/project1/submission_controller")
    try:
        spawner = op("/project1/submission_controller/spawner")
        spawner.module.resetRuntime()
        clearGeneratedPool(controller)
        ensureGeneratedPoolCopies(controller, op("/project1/submission_template"))
        if hasattr(spawner.module, "spawner"):
            spawner.module.spawner.clear_pool_cache()
        if hasattr(spawner.module, "hardRefresh"):
            spawner.module.hardRefresh()
        else:
            spawner.module.manualRefresh()
        op("/project1/auto_wire_preview").module.wirePreviewCards()
        print("Birthday pool rebuilt.")
    except Exception as err:
        print("Birthday pool rebuild failed:", err)


def repairBirthdayPreview():
    project = op("/project1")
    buildPreviewNetwork(project)
    buildPreviewAutoWire(project)
    try:
        op("/project1/auto_wire_preview").module.wirePreviewCards()
    except Exception:
        pass
    forceCookPreview()
    final_out = op("/project1/final_out")
    if final_out:
        print("Preview repaired. final_out: {}x{}".format(final_out.width, final_out.height))


def diagnosePreviewResolution():
    for path in (
        "/project1/preview_bg",
        "/project1/preview_transform_01",
        "/project1/all_cards_comp",
        "/project1/preview_level",
        "/project1/final_out",
    ):
        node = op(path)
        if node:
            print("{}: {}x{}".format(path, node.width, node.height))
        else:
            print("{}: missing".format(path))


def showFirstCardDirect():
    """Debug: bypass preview compositor and show submission_01/out1 directly."""
    card_out = op("/project1/submission_controller/spawner_pool/submission_01/out1")
    final_out = op("/project1/final_out")
    if not card_out or not final_out:
        print("Cannot debug direct card: card_out or final_out missing.")
        return
    disconnect_all_inputs(final_out)
    connect(final_out, card_out, 0)
    force_cook(final_out)
    print("final_out now shows submission_01/out1 directly: {}x{}".format(final_out.width, final_out.height))


def restorePreviewOutput():
    """Reconnect normal preview output chain."""
    preview_level = op("/project1/preview_level")
    final_out = op("/project1/final_out")
    if not preview_level or not final_out:
        print("Cannot restore preview: preview_level or final_out missing.")
        return
    disconnect_all_inputs(final_out)
    connect(final_out, preview_level, 0)
    forceCookPreview()
    print("final_out restored to preview_level: {}x{}".format(final_out.width, final_out.height))


def wireCardsNoTransform():
    """Debug fallback: connect submission out1 TOPs directly to all_cards_comp."""
    comp = op("/project1/all_cards_comp")
    bg = op("/project1/preview_bg")
    if not comp:
        print("Missing /project1/all_cards_comp")
        return
    disconnect_all_inputs(comp)
    if bg:
        connect(comp, bg, 0)
    wired = 0
    for index in range(MAX_PREVIEW_CARDS):
        card_out = op("/project1/submission_controller/spawner_pool/submission_{:02d}/out1".format(index + 1))
        if card_out:
            connect(comp, card_out, index + 1)
            wired += 1
    restorePreviewOutput()
    print("Direct card fallback wired:", wired)


def forceCookPreview():
    for name in ("preview_bg", "all_cards_comp", "preview_level", "final_out", "favorite_wordcloud", "favorite_fit", "favorite_out"):
        force_cook(op("/project1/" + name))

    for index in range(1, MAX_PREVIEW_CARDS + 1):
        force_cook(op("/project1/preview_select_{:02d}".format(index)))
        force_cook(op("/project1/preview_transform_{:02d}".format(index)))


def diagnoseBirthdayTouchDesigner():
    controller = op("/project1/submission_controller")
    spawner = op("/project1/submission_controller/spawner")
    pool = op("/project1/submission_controller/spawner_pool")
    database_table = op("/project1/submission_controller/database_table")
    queue_table = op("/project1/submission_controller/queue_table")
    active_table = op("/project1/submission_controller/active_table")
    stats_table = op("/project1/submission_controller/stats_table")

    print("Birthday TD diagnosis")
    print("controller:", bool(controller), controller.path if controller else None)
    print("spawner:", bool(spawner), spawner.path if spawner else None)
    print("spawner has onFrameStart:", hasattr(spawner.module, "onFrameStart") if spawner else False)
    print("pool:", bool(pool), pool.path if pool else None)
    print("database rows:", database_table.numRows if database_table else None)
    print("queue rows:", queue_table.numRows if queue_table else None)
    print("active rows:", active_table.numRows if active_table else None)
    try:
        with urlopen("http://127.0.0.1:8080/api/submissions", timeout=1.0) as response:
            payload = json.loads(response.read().decode("utf-8"))
            print("backend count:", payload.get("count"))
            print("backend ids:", [item.get("id") for item in payload.get("submissions", [])])
    except Exception as err:
        print("backend check failed:", err)

    if stats_table:
        print("stats rows:", stats_table.numRows)
        for row in range(stats_table.numRows):
            try:
                print("{}: {}".format(stats_table[row, 0].val, stats_table[row, 1].val))
            except Exception:
                pass

    try:
        if hasattr(spawner.module, "hardRefresh"):
            spawner.module.hardRefresh()
            print("hardRefresh executed")
        else:
            spawner.module.manualRefresh()
            print("manualRefresh executed")
    except Exception as err:
        print("refresh failed:", err)

    diagnoseBirthdayVisuals()


def diagnoseBirthdayVisuals():
    try:
        op("/project1/auto_wire_preview").module.wirePreviewCards()
    except Exception:
        pass

    print("Birthday visual diagnosis")
    card = op("/project1/submission_controller/spawner_pool/submission_01")
    pool = op("/project1/submission_controller/spawner_pool")
    photo = op("/project1/submission_controller/spawner_pool/submission_01/photo")
    name_text = op("/project1/submission_controller/spawner_pool/submission_01/name_text")
    message_text = op("/project1/submission_controller/spawner_pool/submission_01/message_text")
    card_out = op("/project1/submission_controller/spawner_pool/submission_01/out1")
    select_01 = op("/project1/preview_select_01")
    transform_01 = op("/project1/preview_transform_01")
    all_cards = op("/project1/all_cards_comp")
    final_out = op("/project1/final_out")

    print("card 01:", bool(card), card.path if card else None)
    print("pool child count:", len(pool.children) if pool else None)
    if card:
        for par_name in ("Posx", "Posy", "Cardsx", "Cardsy"):
            try:
                print("{}: {}".format(par_name, getattr(card.par, par_name).eval()))
            except Exception:
                print("{}: missing".format(par_name))
    print("photo 01:", bool(photo), photo.path if photo else None)
    if photo:
        try:
            photo_file = photo.par.file.eval()
            print("photo file:", photo_file)
            print("photo file exists:", Path(photo_file).exists() if photo_file else False)
            print("photo size:", getattr(photo, "width", None), getattr(photo, "height", None))
            print("photo warnings:", photo.warnings() if hasattr(photo, "warnings") else "")
            print("photo errors:", photo.errors() if hasattr(photo, "errors") else "")
        except Exception as err:
            print("photo file read failed:", err)

    print("name_text:", bool(name_text), name_text.path if name_text else None)
    if name_text:
        try:
            print("name_text value:", name_text.par.text.eval())
            print("name_text size:", getattr(name_text, "width", None), getattr(name_text, "height", None))
        except Exception as err:
            print("name_text read failed:", err)

    print("message_text:", bool(message_text), message_text.path if message_text else None)
    if message_text:
        try:
            print("message_text value:", message_text.par.text.eval())
            print("message_text size:", getattr(message_text, "width", None), getattr(message_text, "height", None))
        except Exception as err:
            print("message_text read failed:", err)

    print("card out1:", bool(card_out), card_out.path if card_out else None)
    if card_out:
        try:
            print("card out1 size:", getattr(card_out, "width", None), getattr(card_out, "height", None))
            print("card out1 warnings:", card_out.warnings() if hasattr(card_out, "warnings") else "")
            print("card out1 errors:", card_out.errors() if hasattr(card_out, "errors") else "")
        except Exception as err:
            print("card out1 read failed:", err)
    print("preview_select_01:", bool(select_01), select_01.path if select_01 else None)
    if select_01:
        try:
            print("preview_select_01 top:", select_01.par.top.eval())
        except Exception as err:
            print("preview_select_01 top read failed:", err)

    print("preview_transform_01:", bool(transform_01), transform_01.path if transform_01 else None)
    if transform_01:
        try:
            print("preview_transform_01 size:", transform_01.width, transform_01.height)
            print("preview_transform_01 errors:", transform_01.errors() if hasattr(transform_01, "errors") else "")
            print("preview_transform_01 warnings:", transform_01.warnings() if hasattr(transform_01, "warnings") else "")
        except Exception as err:
            print("preview_transform_01 read failed:", err)

    print("all_cards_comp:", bool(all_cards), all_cards.path if all_cards else None)
    if all_cards:
        try:
            connected = []
            for index, input_op in enumerate(all_cards.inputs):
                if input_op:
                    connected.append("{}:{}".format(index, input_op.path))
            print("all_cards connected inputs:", connected)
        except Exception as err:
            print("all_cards input read failed:", err)

    print("final_out:", bool(final_out), final_out.path if final_out else None)
    if final_out:
        try:
            print("final_out size:", final_out.width, final_out.height)
            print("final_out warnings:", final_out.warnings() if hasattr(final_out, "warnings") else "")
            print("final_out errors:", final_out.errors() if hasattr(final_out, "errors") else "")
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Controller
# ---------------------------------------------------------------------------


def buildController(project):
    controller = ensure_comp(project, "submission_controller", baseCOMP, 0, 0)

    ensure_table(controller, "database_table", 0, 0)
    ensure_table(controller, "queue_table", 180, 0)
    ensure_table(controller, "active_table", 360, 0)
    ensure_table(controller, "stats_table", 540, 0)
    ensure_table(controller, "favorite_table", 720, 0)

    ensure_comp(controller, "spawner_pool", baseCOMP, 0, -180)

    spawner = ensure_dat(controller, "spawner", textDAT, 0, 180)
    installSpawnerFramework(spawner)

    execute = ensure_dat(controller, "execute_spawner", executeDAT, 190, 180)
    set_par(execute, "framestart", True)
    execute.text = (
        "def onFrameStart(frame):\n"
        "    op('/project1/submission_controller/spawner').module.onFrameStart(frame)\n"
        "    return\n"
    )
    buildOscReceiver(controller)

    return controller


def buildOscReceiver(controller):
    callbacks = ensure_dat(controller, "osc_submission_callbacks", textDAT, 390, 180)
    callbacks.text = (
        "def onReceiveOSC(dat, rowIndex, message, bytes, timeStamp, address, args, peer):\n"
        "    if address != '{address}':\n"
        "        return\n"
        "    payload = args[0] if args else ''\n"
        "    op('/project1/submission_controller/spawner').module.onOscSubmission(payload)\n"
        "    return\n"
    ).format(address=OSC_SUBMISSION_ADDRESS)

    try:
        osc_in = ensure_dat(controller, "osc_submission_in", oscinDAT, 390, 20)
    except Exception as err:
        print("OSC In DAT creation skipped:", err)
        return None

    for par_name in ("active", "listen"):
        set_par(osc_in, par_name, True)
    for par_name in ("port", "localport", "networkport"):
        set_par(osc_in, par_name, OSC_IN_PORT)
    for par_name in ("callbacks", "callbackdat"):
        set_par(osc_in, par_name, callbacks.path)

    print("OSC receiver ready on port {} address {}".format(OSC_IN_PORT, OSC_SUBMISSION_ADDRESS))
    return osc_in


def installSpawnerFramework(spawner):
    if not spawner:
        return False

    try:
        framework = SPAWNER_FRAMEWORK_FILE.read_text(encoding="utf-8")
    except Exception as err:
        spawner.text = (
            "Could not read td_spawner_framework.py from:\n"
            "{}\n\n"
            "Error:\n"
            "{}\n\n"
            "Paste the file contents here manually."
        ).format(SPAWNER_FRAMEWORK_FILE, err)
        print("Spawner framework install failed: {}".format(err))
        return False

    if "class BirthdaySpawner" not in framework:
        print("Spawner framework file found, but contents look invalid.")
        return False

    try:
        if spawner.text == framework:
            print("Spawner runtime already up to date in {}".format(spawner.path))
            return True
    except Exception:
        pass

    spawner.text = framework
    try:
        spawner.cook(force=True)
    except Exception:
        pass
    try:
        spawner.par.reinitnet.pulse()
    except Exception:
        pass
    print("Installed spawner runtime into {}".format(spawner.path))
    return True


def startBirthdayRuntime():
    try:
        spawner = op("/project1/submission_controller/spawner")
    except Exception as err:
        print("Spawner runtime lookup failed:", err)
        spawner = None

    active_runtime = spawnerHasActiveRuntime(spawner)
    if spawner:
        if active_runtime:
            print("Spawner runtime already active; keeping current entries.")
        else:
            try:
                spawner.cook(force=True)
            except Exception:
                pass
            try:
                spawner.par.reinitnet.pulse()
            except Exception:
                pass

    try:
        spawner = op("/project1/submission_controller/spawner")
        if spawnerHasActiveRuntime(spawner):
            print("Spawner runtime refresh skipped; active entries preserved.")
        else:
            spawner.module.manualRefresh()
            print("Spawner runtime refreshed.")
    except Exception as err:
        print("Spawner runtime refresh skipped:", err)

    try:
        op("/project1/auto_wire_preview").module.wirePreviewCards()
    except Exception as err:
        print("Preview auto-wire skipped:", err)


def spawnerHasActiveRuntime(spawner):
    if not spawner:
        return False
    try:
        module_spawner = spawner.module.spawner
        return bool(module_spawner.active or module_spawner.queue)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Submission visual template
# ---------------------------------------------------------------------------


def buildSubmissionTemplate(project):
    template = ensure_comp(project, "submission_template", baseCOMP, 560, 0)

    photo = ensure_photo_loader(template, "photo", 0, 0)
    fit_photo = ensure_top(template, "fit_photo", fitTOP, 170, 0)
    level_photo = ensure_top(template, "level_photo", levelTOP, 340, 0)
    photo_layout = ensure_top(template, "photo_layout", transformTOP, 510, 0)

    card_bg = ensure_top(template, "card_bg", constantTOP, 0, -150)
    name_text = ensure_top(template, "name_text", textTOP, 0, -310)
    level_name = ensure_top(template, "level_name", levelTOP, 170, -310)
    name_layout = ensure_top(template, "name_layout", transformTOP, 340, -310)
    message_text = ensure_top(template, "message_text", textTOP, 0, -470)
    level_message = ensure_top(template, "level_message", levelTOP, 170, -470)
    message_layout = ensure_top(template, "message_layout", transformTOP, 340, -470)

    composite_card = ensure_top(template, "composite_card", compositeTOP, 720, -150)
    final_level = ensure_top(template, "final_level", levelTOP, 920, -150)
    out1 = ensure_top(template, "out1", nullTOP, 1100, -150)
    opacity = ensure_chop(template, "opacity", constantCHOP, 560, -360)

    set_par(fit_photo, "fit", "fit")
    set_par(fit_photo, "justifyx", "center")
    set_par(fit_photo, "justifyy", "center")
    set_par(card_bg, "colorr", 0.0)
    set_par(card_bg, "colorg", 0.0)
    set_par(card_bg, "colorb", 0.0)
    set_par(card_bg, "alpha", 0.0)
    set_resolution(photo, ENTRY_WIDTH, ENTRY_HEIGHT)
    set_resolution(fit_photo, ENTRY_WIDTH, ENTRY_HEIGHT)
    set_resolution(level_photo, ENTRY_WIDTH, ENTRY_HEIGHT)
    set_resolution(card_bg, ENTRY_WIDTH, ENTRY_HEIGHT)
    set_resolution(photo_layout, ENTRY_WIDTH, ENTRY_HEIGHT)
    set_resolution(name_layout, ENTRY_WIDTH, ENTRY_HEIGHT)
    set_resolution(message_layout, ENTRY_WIDTH, ENTRY_HEIGHT)
    set_resolution(composite_card, ENTRY_WIDTH, ENTRY_HEIGHT)
    set_resolution(final_level, ENTRY_WIDTH, ENTRY_HEIGHT)
    set_resolution(out1, ENTRY_WIDTH, ENTRY_HEIGHT)
    configure_entry_layout_transform(photo_layout, 0, 0, 1.0, 1.0)

    set_par(name_text, "text", "Nama Pengirim")
    set_par(name_text, "fontsize", 54)
    set_par(name_text, "fontcolorr", 1.0)
    set_par(name_text, "fontcolorg", 1.0)
    set_par(name_text, "fontcolorb", 1.0)
    set_par(name_text, "fontcolora", 1.0)
    set_par(name_text, "bgcolora", 0.0)
    set_par(name_text, "bgalpha", 0.0)
    set_par(name_text, "alignx", "left")
    set_par(name_text, "aligny", "center")
    configure_entry_layout_transform(name_layout, 0, 0, 1.0, 1.0)
    set_par(message_text, "text", "Pesan ucapan tampil di sini")
    set_par(message_text, "fontsize", 34)
    set_par(message_text, "fontcolorr", 1.0)
    set_par(message_text, "fontcolorg", 1.0)
    set_par(message_text, "fontcolorb", 1.0)
    set_par(message_text, "fontcolora", 1.0)
    set_par(message_text, "bgcolora", 0.0)
    set_par(message_text, "bgalpha", 0.0)
    set_par(message_text, "alignx", "left")
    set_par(message_text, "aligny", "top")
    configure_entry_layout_transform(message_layout, 0, 0, 1.0, 1.0)
    set_par(opacity, "value0", 0)
    clear_expression(final_level, "opacity")
    set_par(final_level, "opacity", 1.0)

    set_par(composite_card, "operand", "over")

    connect(fit_photo, photo, 0)
    connect(level_photo, fit_photo, 0)
    connect(photo_layout, level_photo, 0)
    connect(level_name, name_text, 0)
    connect(name_layout, level_name, 0)
    connect(level_message, message_text, 0)
    connect(message_layout, level_message, 0)
    # Composite TOP Over treats earlier inputs as upper layers in many TD builds.
    # Put text/photo first, and the white card background last.
    connect(composite_card, name_layout, 0)
    connect(composite_card, message_layout, 1)
    connect(composite_card, photo_layout, 2)
    connect(composite_card, card_bg, 3)
    connect(final_level, photo_layout, 0)
    # The web server now renders the complete 16:9 card. Keep the older text
    # nodes for metadata/debugging, but send only the composed card to output.
    connect(out1, photo_layout, 0)

    set_par(template, "display", False)
    set_par(template, "render", False)
    return template


# ---------------------------------------------------------------------------
# Preview output
# ---------------------------------------------------------------------------


def buildPreviewNetwork(project):
    bg = ensure_top(project, "preview_bg", constantTOP, -220, -520)
    composite = ensure_top(project, "all_cards_comp", compositeTOP, 0, -520)
    level = ensure_top(project, "preview_level", levelTOP, 220, -520)
    final_out = ensure_top(project, "final_out", nullTOP, 420, -520)
    window = ensure_comp(project, "window1", windowCOMP, 620, -520)

    set_par(bg, "colorr", 0.0)
    set_par(bg, "colorg", 0.0)
    set_par(bg, "colorb", 0.0)
    # Keep this transparent for now. In some TouchDesigner Composite TOP modes,
    # a later opaque input can cover every spawned entry.
    set_par(bg, "alpha", 0.0)
    set_resolution(bg, CANVAS_WIDTH, CANVAS_HEIGHT)
    set_resolution(composite, CANVAS_WIDTH, CANVAS_HEIGHT)
    set_resolution(level, CANVAS_WIDTH, CANVAS_HEIGHT)
    set_resolution(final_out, CANVAS_WIDTH, CANVAS_HEIGHT)
    set_par(composite, "operand", "over")

    cleanLegacyPreviewNodes(project)
    disconnect_all_inputs(composite)
    connect(composite, bg, 0)
    buildPreviewSelects(project, composite)
    connect(level, composite, 0)
    connect(final_out, level, 0)

    try:
        window.par.winopen.pulse()
    except Exception:
        pass

    try:
        window.par.operator = final_out.path
    except Exception:
        pass

    return final_out


def buildPreviewSelects(project, composite):
    for index in range(MAX_PREVIEW_CARDS):
        number = index + 1
        select_name = "preview_select_{:02d}".format(number)
        transform_name = "preview_transform_{:02d}".format(number)
        select_top = ensure_top(project, select_name, selectTOP, -420, -640 - (index * 80))
        transform_top = ensure_top(project, transform_name, transformTOP, -220, -640 - (index * 80))
        target = "/project1/submission_controller/spawner_pool/submission_{:02d}/out1".format(number)
        set_par(select_top, "top", target)
        connect(transform_top, select_top, 0)
        configure_preview_transform(transform_top, number)
        connect(composite, transform_top, index + 1)


def configure_preview_transform(transform_top, number):
    comp_path = "/project1/submission_controller/spawner_pool/submission_{:02d}".format(number)
    set_par(transform_top, "unit", "fraction")
    set_resolution(transform_top, CANVAS_WIDTH, CANVAS_HEIGHT)
    set_par(transform_top, "fillmode", "fit")
    set_par(transform_top, "extend", "zero")
    set_expression(transform_top, "tx", "max(-0.3, min(0.3, ((op('{}').par.Posx.eval() if op('{}') and hasattr(op('{}').par, 'Posx') else {}) / {}) - 0.5))".format(comp_path, comp_path, comp_path, CANVAS_WIDTH / 2, CANVAS_WIDTH))
    set_expression(transform_top, "ty", "max(-0.3, min(0.3, 0.5 - ((op('{}').par.Posy.eval() if op('{}') and hasattr(op('{}').par, 'Posy') else {}) / {})))".format(comp_path, comp_path, comp_path, CANVAS_HEIGHT / 2, CANVAS_HEIGHT))
    set_expression(transform_top, "sx", "op('{}').par.Cardsx if op('{}') and hasattr(op('{}').par, 'Cardsx') else 0.1".format(comp_path, comp_path, comp_path))
    set_expression(transform_top, "sy", "op('{}').par.Cardsy if op('{}') and hasattr(op('{}').par, 'Cardsy') else 0.1".format(comp_path, comp_path, comp_path))


def cleanLegacyPreviewNodes(project):
    for index in range(1, MAX_PREVIEW_CARDS + 1):
        for prefix in ("preview_canvas_", "preview_slot_comp_"):
            node = project.op("{}{:02d}".format(prefix, index))
            if node:
                try:
                    node.destroy()
                except Exception:
                    pass


def buildFavoriteWindow(project):
    wordcloud = ensure_photo_loader(project, "favorite_wordcloud", -220, -900)
    fit = ensure_top(project, "favorite_fit", fitTOP, 0, -900)
    out = ensure_top(project, "favorite_out", nullTOP, 220, -900)
    window = ensure_comp(project, "favorite_window", windowCOMP, 420, -900)

    wordcloud_path = str(PROJECT_ROOT / "data" / "wordcloud" / "favorite_wordcloud.png").replace("\\", "/")
    for par_name in ("file", "filename", "image"):
        set_par(wordcloud, par_name, wordcloud_path)

    set_par(fit, "fit", "fit")
    set_par(fit, "justifyx", "center")
    set_par(fit, "justifyy", "center")
    set_resolution(wordcloud, CANVAS_WIDTH, CANVAS_HEIGHT)
    set_resolution(fit, CANVAS_WIDTH, CANVAS_HEIGHT)
    set_resolution(out, CANVAS_WIDTH, CANVAS_HEIGHT)

    connect(fit, wordcloud, 0)
    connect(out, fit, 0)

    try:
        window.par.operator = out.path
    except Exception:
        pass

    try:
        window.par.winopen.pulse()
    except Exception:
        pass

    return out


def configure_entry_layout_transform(transform_top, tx, ty, sx, sy):
    set_par(transform_top, "unit", "pixels")
    set_resolution(transform_top, ENTRY_WIDTH, ENTRY_HEIGHT)
    clear_expression(transform_top, "tx")
    clear_expression(transform_top, "ty")
    clear_expression(transform_top, "sx")
    clear_expression(transform_top, "sy")
    set_par(transform_top, "tx", tx)
    set_par(transform_top, "ty", ty)
    set_par(transform_top, "sx", sx)
    set_par(transform_top, "sy", sy)


def buildPreviewAutoWire(project):
    wire = ensure_dat(project, "auto_wire_preview", textDAT, 0, -700)
    wire.text = (
        "def wirePreviewCards():\n"
        "    comp = op('/project1/all_cards_comp')\n"
        "    bg = op('/project1/preview_bg')\n"
        "    if not comp:\n"
        "        return 0\n"
        "    if bg:\n"
        "        try:\n"
        "            comp.setInput(0, bg)\n"
        "        except Exception:\n"
        "            pass\n"
        "    wired = 0\n"
        "    for i in range({max_cards}):\n"
        "        number = i + 1\n"
        "        select_top = op('/project1/preview_select_{{:02d}}'.format(number))\n"
        "        transform_top = op('/project1/preview_transform_{{:02d}}'.format(number))\n"
        "        target = '/project1/submission_controller/spawner_pool/submission_{{:02d}}/out1'.format(number)\n"
        "        if select_top and transform_top:\n"
        "            try:\n"
        "                select_top.par.top = target\n"
        "                transform_top.setInput(0, select_top)\n"
        "                comp.setInput(i + 1, transform_top)\n"
        "                wired += 1\n"
        "            except Exception:\n"
        "                pass\n"
        "    if wired:\n"
        "        print('Preview select TOPs wired: {{}} into /project1/all_cards_comp'.format(wired))\n"
        "    return wired\n"
    ).format(max_cards=MAX_PREVIEW_CARDS)

    execute = ensure_dat(project, "execute_auto_wire_preview", executeDAT, 220, -700)
    set_par(execute, "framestart", True)
    try:
        execute.store("preview_wired", False)
    except Exception:
        pass
    execute.text = (
        "def onFrameStart(frame):\n"
        "    if me.fetch('preview_wired', False):\n"
        "        return\n"
        "    try:\n"
        "        wired = op('auto_wire_preview').module.wirePreviewCards()\n"
        "        if wired:\n"
        "            me.store('preview_wired', True)\n"
        "    except Exception:\n"
        "        pass\n"
        "    return\n"
    )


# ---------------------------------------------------------------------------
# Operator controls
# ---------------------------------------------------------------------------


def buildControlPanel(project):
    controls = ensure_dat(project, "birthday_controls", textDAT, 440, -700)
    controls.text = (
        "def manualRefresh():\n"
        "    op('/project1/submission_controller/spawner').module.manualRefresh()\n"
        "\n"
        "def hardRefresh():\n"
        "    op('/project1/submission_controller/spawner').module.hardRefresh()\n"
        "\n"
        "def resetRuntime():\n"
        "    op('/project1/submission_controller/spawner').module.resetRuntime()\n"
        "\n"
        "def enableSpawner():\n"
        "    op('/project1/submission_controller/spawner').module.setEnabled(True)\n"
        "\n"
        "def disableSpawner():\n"
        "    op('/project1/submission_controller/spawner').module.setEnabled(False)\n"
        "\n"
        "def wirePreview():\n"
        "    op('/project1/auto_wire_preview').module.wirePreviewCards()\n"
    )
    return controls


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def ensure_comp(parent_comp, name, op_type, x, y):
    existing = parent_comp.op(name)
    if existing:
        return existing
    created = parent_comp.create(op_type, name)
    created.nodeX = x
    created.nodeY = y
    return created


def ensure_top(parent_comp, name, op_type, x, y):
    existing = parent_comp.op(name)
    if existing:
        return existing
    created = parent_comp.create(op_type, name)
    created.nodeX = x
    created.nodeY = y
    return created


def ensure_photo_loader(parent_comp, name, x, y):
    existing = parent_comp.op(name)
    if existing:
        try:
            existing.destroy()
        except Exception:
            return existing

    # Image File In TOP is more reliable for still images. Some TD builds may
    # not expose it, so fallback to Movie File In TOP.
    try:
        created = parent_comp.create(imagefileinTOP, name)
    except Exception:
        created = parent_comp.create(moviefileinTOP, name)

    created.nodeX = x
    created.nodeY = y
    return created


def ensure_chop(parent_comp, name, op_type, x, y):
    existing = parent_comp.op(name)
    if existing:
        return existing
    created = parent_comp.create(op_type, name)
    created.nodeX = x
    created.nodeY = y
    return created


def ensure_dat(parent_comp, name, op_type, x, y):
    existing = parent_comp.op(name)
    if existing:
        return existing
    created = parent_comp.create(op_type, name)
    created.nodeX = x
    created.nodeY = y
    return created


def ensure_table(parent_comp, name, x, y):
    return ensure_dat(parent_comp, name, tableDAT, x, y)


def connect(target, source, input_index=0):
    if not target or not source:
        return False
    try:
        target.inputConnectors[input_index].connect(source)
        return True
    except Exception:
        pass
    try:
        target.setInput(input_index, source)
        return True
    except Exception:
        return False


def disconnect_all_inputs(operator):
    if not operator:
        return
    try:
        for connector in operator.inputConnectors:
            try:
                connector.disconnect()
            except Exception:
                pass
    except Exception:
        pass
    try:
        for index in range(len(operator.inputs)):
            try:
                operator.setInput(index, None)
            except Exception:
                pass
    except Exception:
        pass


def set_par(operator, par_name, value):
    if not operator:
        return False
    try:
        getattr(operator.par, par_name).val = value
        return True
    except Exception:
        return False


def set_resolution(operator, width, height):
    if not operator:
        return False

    for value in ("custom", "Custom", 9, 8, 1):
        if set_par(operator, "outputresolution", value):
            break

    success = False
    for x_name, y_name in (
        ("resolutionw", "resolutionh"),
        ("resolution1", "resolution2"),
        ("resw", "resh"),
        ("res1", "res2"),
        ("sizex", "sizey"),
        ("w", "h"),
        ("width", "height"),
    ):
        ok_x = set_par(operator, x_name, width)
        ok_y = set_par(operator, y_name, height)
        if ok_x and ok_y:
            success = True

    force_cook(operator)
    return success


def set_expression(operator, par_name, expression):
    if not operator:
        return False
    try:
        getattr(operator.par, par_name).expr = expression
        return True
    except Exception:
        return False


def clear_expression(operator, par_name):
    if not operator:
        return False
    try:
        par = getattr(operator.par, par_name)
        par.expr = ""
        return True
    except Exception:
        return False


def force_cook(operator):
    if not operator:
        return False
    try:
        operator.cook(force=True)
        return True
    except Exception:
        return False
