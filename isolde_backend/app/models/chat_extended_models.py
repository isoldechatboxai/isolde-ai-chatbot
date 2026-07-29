from app.extensions import db
from datetime import datetime

class ChatFolder(db.Model):
    """Module 1: Groups conversations into custom folders."""
    __tablename__ = 'ext_chat_folders' # Changed to avoid conflicts
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(100), nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
class ChatTag(db.Model):
    """Module 1: Allows tagging conversations for search/filtering."""
    __tablename__ = 'ext_chat_tags' # Changed to avoid conflicts
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(100), nullable=False, index=True)
    name = db.Column(db.String(50), nullable=False)
    color_code = db.Column(db.String(20), default="#808080")

class ConversationTagMap(db.Model):
    """Mapping table for Many-to-Many relationship between Conversations and Tags."""
    __tablename__ = 'ext_conversation_tag_map' # Changed to avoid conflicts
    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.String(100), nullable=False, index=True)
    tag_id = db.Column(db.Integer, db.ForeignKey('ext_chat_tags.id', ondelete='CASCADE'), nullable=False)

class PinnedChat(db.Model):
    """Module 1: Tracks pinned and favorite conversations per user."""
    __tablename__ = 'ext_pinned_chats' # Changed to avoid conflicts
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(100), nullable=False, index=True)
    conversation_id = db.Column(db.String(100), nullable=False, unique=True)
    is_favorite = db.Column(db.Boolean, default=False)
    pinned_at = db.Column(db.DateTime, default=datetime.utcnow)

class MessageReaction(db.Model):
    """Module 2: Stores user emojis/reactions to specific AI or User messages."""
    __tablename__ = 'ext_message_reactions' # Changed to avoid conflicts
    id = db.Column(db.Integer, primary_key=True)
    message_id = db.Column(db.Integer, nullable=False, index=True) 
    user_id = db.Column(db.String(100), nullable=False)
    emoji = db.Column(db.String(20), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Bookmark(db.Model):
    """Module 2: Bookmarks specific messages for quick reference."""
    __tablename__ = 'ext_bookmarks' # 🌟 FIXED: Changed from 'bookmarks' to 'ext_bookmarks'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(100), nullable=False, index=True)
    message_id = db.Column(db.Integer, nullable=False) 
    note = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class ConversationAnalytics(db.Model):
    """Module 13: Tracks token usage, cost, and metadata per conversation."""
    __tablename__ = 'ext_conversation_analytics' # Changed to avoid conflicts
    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.String(100), nullable=False, unique=True, index=True)
    total_tokens = db.Column(db.Integer, default=0)
    total_cost = db.Column(db.Float, default=0.0)
    ai_model_used = db.Column(db.String(50), nullable=True)
    message_count = db.Column(db.Integer, default=0)
    last_activity = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)