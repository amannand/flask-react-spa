""" Flask Application Factory Pattern
http://flask.pocoo.org/docs/0.11/patterns/appfactories/

Conventions to follow for magic to ensue:

VIEWS, MODELS, and COMMANDS ("bundles")
-----------------------------
All views/models should be contained in bundle folders.
Views should be in a file named `views.py` containing the flask.Blueprint instance.
Models should be in a file named `models.py` and should extend database.Model
Commands should be in a file named `commands.py` containing a click.Group instance.
Finally, each bundle folder must be registered in `config.py`

EXTENSIONS
-----------------------------
All extensions should be instantiated in `extensions.py`

CLI COMMANDS
-----------------------------
Decorate custom CLI commands in `commands.py` using @cli.command()

FLASK SHELL CONTEXT
-----------------------------
Database models and app extensions will automatically be added to
the shell context, presuming the above conventions have been followed.
"""
import sys
from flask import Flask, session
from flask_wtf.csrf import generate_csrf

from .logger import logger
from .magic import (
    get_bundle_blueprints,
    get_bundle_command_groups,
    get_bundle_models,
    get_commands,
    get_deferred_extensions,
    get_extensions,
)


def create_app(config_object, **kwargs):
    """Application factory pattern

    WARNING: HERE BE DRAGONS!!! DO NOT FUCK WITH THE ORDER OF THESE or nightmares will ensue
    """
    app = Flask(__name__, **kwargs)
    configure_app(app, config_object)

    extensions = dict(get_extensions())
    register_extensions(app, extensions)

    register_blueprints(app)
    models = dict(get_bundle_models())

    deferred_extensions = dict(get_deferred_extensions())
    register_extensions(app, deferred_extensions)

    register_cli_commands(app)
    register_shell_context(app, extensions, deferred_extensions, models)

    return app


def configure_app(app, config_object):
    app.config.from_object(config_object)

    @app.before_request
    def enable_session_timeout():
        session.permanent = True  # set session to use PERMANENT_SESSION_LIFETIME
        session.modified = True   # reset the session timer on every request

    @app.after_request
    def set_csrf_cookie(response):
        if response:
            response.set_cookie('csrf_token', generate_csrf())
        return response


def register_extensions(app, extensions):
    """Register and initialize extensions"""
    for extension in extensions.values():
        extension.init_app(app)


def register_blueprints(app):
    """Register bundle views"""
    # disable strict_slashes on all routes by default
    if not app.config.get('STRICT_SLASHES', False):
        app.url_map.strict_slashes = False
    # register blueprints
    for blueprint, url_prefix in get_bundle_blueprints():
        app.register_blueprint(blueprint, url_prefix=url_prefix)


def register_shell_context(app, extensions, deferred_extensions, models):
    """Register variables to automatically import when running `flask shell`"""
    def shell_context():
        ctx = {}
        ctx.update(extensions)
        ctx.update(deferred_extensions)
        ctx.update(models)
        return ctx
    app.shell_context_processor(shell_context)


def register_cli_commands(app):
    """Register all the Click commands declared in commands.py and
    each bundle's commands.py"""
    commands = list(get_commands())
    commands += list(get_bundle_command_groups())
    for name, command in commands:
        if name in app.cli.commands:
            logger.error('Command name conflict: "%s" is taken.' % name)
            sys.exit(1)
        app.cli.add_command(command)
