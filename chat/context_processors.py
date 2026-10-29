from .services import unread_count_for


def unread_chat_count(request):
    if request.user.is_authenticated:
        return {'unread_chat_count': unread_count_for(request.user)}
    return {'unread_chat_count': 0}
