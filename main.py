from datetime import date
from flask import Flask, abort, render_template, redirect, url_for, flash, jsonify
from flask_bootstrap import Bootstrap5
from flask_ckeditor import CKEditor
from flask_gravatar import Gravatar
from flask_login import UserMixin, login_user, LoginManager, current_user, logout_user, login_required
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship, DeclarativeBase, Mapped, mapped_column
from sqlalchemy import Integer, String, Text
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
import os
# Import your forms from the forms.py
from forms import CreatePostForm, RegisterForm, LoginForm, CommentForm


app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('FLASK_KEY')
ckeditor = CKEditor(app)
Bootstrap5(app)
login_manager = LoginManager()
login_manager.init_app(app)


# CREATE DATABASE
class Base(DeclarativeBase):
    pass
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('POSTGRESQL_DB', 'SQLALCHEMY_DB')
db = SQLAlchemy(model_class=Base)
db.init_app(app)


# CONFIGURE TABLES
class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Create Foreign Key, "users.id" the users refers to the tablename of User.
    author_id: Mapped[int] = mapped_column(Integer, db.ForeignKey("users.id"))
    # Create reference to the User object. The "posts" refers to the posts property in the User class.
    author = relationship("User", back_populates="posts")
    title: Mapped[str] = mapped_column(String(250), unique=True, nullable=False)
    subtitle: Mapped[str] = mapped_column(String(250), nullable=False)
    date: Mapped[str] = mapped_column(String(250), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    img_url: Mapped[str] = mapped_column(String(250), nullable=False)
    # Parent relationship to the comments
    comments = relationship("Comment", back_populates="parent_post")


# Create a User table for all your registered users
class User(UserMixin, db.Model):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(100), unique=True)
    password: Mapped[str] = mapped_column(String(100))
    name: Mapped[str] = mapped_column(String(100))
    # This will act like a list of BlogPost objects attached to each User.
    # The "author" refers to the author property in the BlogPost class.
    posts = relationship("BlogPost", back_populates="author")
    # Parent relationship: "comment_author" refers to the comment_author property in the Comment class.
    comments = relationship("Comment", back_populates="comment_author")


# Create a table for the comments on the blog posts
class Comment(db.Model):
    __tablename__ = "comments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    # Child relationship:"users.id" The users refers to the tablename of the User class.
    # "comments" refers to the comments property in the User class.
    author_id: Mapped[int] = mapped_column(Integer, db.ForeignKey("users.id"))
    comment_author = relationship("User", back_populates="comments")
    # Child Relationship to the BlogPosts
    post_id: Mapped[str] = mapped_column(Integer, db.ForeignKey("blog_posts.id"))
    parent_post = relationship("BlogPost", back_populates="comments")


with app.app_context():
    db.create_all()


gravatar = Gravatar(
            app,
            size=100,
            rating='g',
            default='retro',
            force_default=False,
            force_lower=False,
            use_ssl=False,
            base_url=None
        )


# TODO: Configure Flask-Login
# This function does not need to be called anywhere!
@login_manager.user_loader
def load_user(user_id):
    return db.get_or_404(User, user_id)


# Helper function(decorator)
def get_current_user(func):
    def wrapper(*args, **kwargs):
        if current_user and hasattr(current_user, 'name') and hasattr(current_user, 'is_authenticated'):
            the_current_user = current_user.name
            if the_current_user:
                print(f"\nUser: {the_current_user} is authenticated: {current_user.is_authenticated}\n")
            else:
                print(f"\nUser not authenticated!")
        else:
            print(f"\nUser NOT logged in!\n")

        return func(*args, **kwargs)

    wrapper.__name__ = func.__name__
    return wrapper


# Get all users
@app.route("/all-users")
def get_all_users():
    result = db.session.execute(db.select(User))
    all_users = result.scalars().all()

    user_dict = {'users': {}}
    for user in all_users:
        user_dict['users'][user.name] = {
                    'id': user.id,
                    'name': user.name,
                    'email': user.email
                }

    return jsonify(user_dict)


# login_required decorator
def admin_only(f):
    @wraps(f)
    @login_required
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated and current_user.id != 1:
            return abort(403)
        return f(*args, **kwargs)
    return wrapper



# TODO: Use Werkzeug to hash the user's password when creating a new user.
@app.route('/register', methods=['GET', 'POST'])
@get_current_user
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        user_email = form.email.data
        user_password = form.password.data
        user_name = form.name.data

        duplicate_email = db.session.execute(db.select(User).where(User.email == user_email))
        user = duplicate_email.scalar()
    
        if user:
            flash("You already have an account with this email, please login.")
            return redirect(url_for('login'))
        else:
            print(f"\nAdding user: '{user_name}' to database\n")

            hashed_and_salted_pwd = generate_password_hash(
                    user_password,
                    method='pbkdf2:sha256',
                    salt_length=8
                )
        
            new_user = User(
                    email=user_email,
                    password=hashed_and_salted_pwd,
                    name=user_name
                )

            db.session.add(new_user)
            db.session.commit()
            
            login_user(new_user)
        
            print(f"Name: {new_user.name}")
            print(f"Email: {new_user.email}")
            print(f"Password: {new_user.password}\n")
            return redirect(url_for('get_all_posts'))

    return render_template("register.html", form=form, logged_in=current_user.is_authenticated)


# TODO: Retrieve a user from the database based on their email. 
@app.route('/login', methods=['GET', 'POST'])
@get_current_user
def login():
    form = LoginForm()

    if form.validate_on_submit():
        user_email = form.email.data
        user_password = form.password.data
    
        existing_user = db.session.execute(db.select(User).where(User.email == user_email))
        user = existing_user.scalar()

        # For debugging purposes
        result = db.session.execute(db.select(User))
        all_users = result.scalars().all()
        
        print(f"\nall existing user emails: {[user.email for user in all_users]}")
        print(f"all existing usernames: {[user.name for user in all_users]}\n")
    
        if not user:
            flash("That email does not exist, please try again.")
            return redirect(url_for('login'))
        elif not check_password_hash(user.password, user_password):
            flash("Password incorrect, please try again.")
            return redirect(url_for('login'))
        elif current_user.is_authenticated:
            flash("You are already logged in!")
            return redirect(url_for('login'))
        else:
            login_user(user)
            print(f"\nUser: '{user.name}' successfully logged in")
            print(f"'load_user(user.id).id': {load_user(user.id).id}\n")
            return redirect(url_for('get_all_posts'))

    return render_template("login.html", form=form, logged_in=current_user.is_authenticated)


@app.route('/logout')
@get_current_user
def logout():
    if current_user.is_authenticated:
        logout_user()
        return redirect(url_for('get_all_posts'))

@app.route('/')
@get_current_user
def get_all_posts():
    result = db.session.execute(db.select(BlogPost))
    posts = result.scalars().all()
    return render_template("index.html", all_posts=posts, logged_in=current_user.is_authenticated)


# TODO: Allow logged-in users to comment on posts
@app.route("/post/<int:post_id>", methods=['GET', 'POST'])
@get_current_user
def show_post(post_id):
    requested_post = db.get_or_404(BlogPost, post_id)

    # Add CommentForm
    comment_form = CommentForm()
    if comment_form.validate_on_submit():
        new_comment = Comment(
                text = comment_form.body.data,
                comment_author = current_user,
                parent_post = requested_post
            )

        db.session.add(new_comment)
        db.session.commit()

    return render_template("post.html", post=requested_post, logged_in=current_user.is_authenticated, form=comment_form)


# TODO: Use a decorator so only an admin user can create a new post
@app.route("/new-post", methods=["GET", "POST"])
@admin_only
@get_current_user
def add_new_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            author=current_user,
            date=date.today().strftime("%B %d, %Y")
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("make-post.html", form=form, logged_in=current_user.is_authenticated)


# TODO: Use a decorator so only an admin user can edit a post
@app.route("/edit-post/<int:post_id>", methods=["GET", "POST"])
@admin_only
@get_current_user
def edit_post(post_id):
    post = db.get_or_404(BlogPost, post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        author=post.author,
        body=post.body
    )
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        post.author = current_user
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))
    return render_template("make-post.html", form=edit_form, is_edit=True, logged_in=current_user.is_authenticated)


# TODO: Use a decorator so only an admin user can delete a post
@app.route("/delete/<int:post_id>")
@admin_only
@get_current_user
def delete_post(post_id):
    post_to_delete = db.get_or_404(BlogPost, post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))


@app.route("/about")
@get_current_user
def about():
    return render_template("about.html", logged_in=current_user.is_authenticated)


@app.route("/contact")
@get_current_user
def contact():
    return render_template("contact.html", logged_in=current_user.is_authenticated)


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5002)



