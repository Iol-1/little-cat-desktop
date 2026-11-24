"""Coat palettes; the renderer adds breed-specific patches and face markings."""

SKINS = {
    'black': {
        'name': '黑猫',
        'body': '#181b20', 'body_shadow': '#14161b',
        'face': '#1a1d23', 'face_shadow': '#15171d',
        'arm': '#17191f', 'paw': '#17191f', 'tail': '#15171b',
        'edge': '#30353d', 'seam': '#eff1e4', 'ear': '#36343d',
        'nose': '#88818b', 'mouth': '#7e7782', 'whisker': '#d2ddd4',
        'eye': '#c5e56e', 'eye_light': '#d4f18b', 'pupil': '#17201c',
    },
    'calico': {
        'name': '三花',
        'body': '#f2ecdf', 'body_shadow': '#e3daca',
        'face': '#f8f1e5', 'face_shadow': '#ece3d4',
        'arm': '#efe7d9', 'paw': '#f4eddf', 'tail': '#3b3532',
        'edge': '#9c9184', 'seam': '#8e8173', 'ear': '#dbaaa1',
        'nose': '#bc8985', 'mouth': '#8d7773', 'whisker': '#7e756a',
        'eye': '#c8d87c', 'eye_light': '#e1e9a4', 'pupil': '#31342b',
        'orange': '#ce915b', 'orange_light': '#dcaa75', 'patch': '#38373b',
    },
    'ragdoll': {
        'name': '布偶',
        'body': '#eee9e1', 'body_shadow': '#d9d1c6',
        'face': '#eee9df', 'face_shadow': '#ded6cb',
        'arm': '#e6dfd5', 'paw': '#efe9df', 'tail': '#827c7b',
        'edge': '#a79d93', 'seam': '#8c827c', 'ear': '#bc9c9e',
        'nose': '#b48f98', 'mouth': '#8c7982', 'whisker': '#8b807b',
        'eye': '#8cc8ed', 'eye_light': '#c1e6f4', 'pupil': '#293c4a',
        'point': '#867e7c', 'point_light': '#a79a94', 'white': '#f6f1e7',
    },
}


def _coat(base, **changes):
    """Keep a complete palette while sharing neutral eye/outline defaults."""
    return dict(SKINS[base], **changes)


for skin_id, skin in SKINS.items():
    skin['pattern'] = skin_id
    skin['group'] = '经典伙伴'

SKINS.update({
    'orange_tabby': _coat('calico', name='橘猫', pattern='tabby', group='虎斑家族',
        body='#dda15f', body_shadow='#cc8b4e', face='#edb976', face_shadow='#dfa460',
        arm='#e1a564', paw='#f1c58c', tail='#d79853', edge='#a27147', seam='#71523e',
        ear='#d99783', stripe='#ac693a', bib='#f7d6a5',
        eye='#a7c96b', eye_light='#d1e899'),
    'silver_tabby': _coat('calico', name='银虎斑', pattern='tabby', group='虎斑家族',
        body='#b8bfc4', body_shadow='#a2abb3', face='#d6dce0', face_shadow='#c1c9ce',
        arm='#c0c8cd', paw='#e3e6e6', tail='#afb8c1', edge='#7c8893', seam='#63717b',
        ear='#cda8ad', stripe='#697580', bib='#eef0ed',
        eye='#a6ce80', eye_light='#cde5ad'),
    'brown_tabby': _coat('calico', name='狸花', pattern='tabby', group='虎斑家族',
        body='#94816d', body_shadow='#7f6e5d', face='#b5a187', face_shadow='#a28d74',
        arm='#a18d76', paw='#c5b198', tail='#8b7867', edge='#5e5148', seam='#e0d1b9',
        ear='#b98d83', stripe='#51483f', bib='#d8c7aa',
        eye='#b7ca72', eye_light='#d3dfa0'),
    'blue': _coat('black', name='英短蓝猫', pattern='solid', group='纯色与双色',
        body='#737f95', body_shadow='#606c82', face='#8490a5', face_shadow='#748197',
        arm='#748096', paw='#7c889f', tail='#64738b', edge='#536177', seam='#dce3ed',
        ear='#b596a4', nose='#a8889c', mouth='#5c4f68', whisker='#e3e8ec',
        eye='#ddaa57', eye_light='#f5cf87', pupil='#44372a'),
    'tuxedo': _coat('black', name='黑白燕尾', pattern='tuxedo', group='纯色与双色',
        body='#292c35', body_shadow='#20232a', face='#333640', face_shadow='#242831',
        arm='#2a2e37', paw='#eeeae2', tail='#282d35', edge='#60616a', seam='#e6e3dc',
        ear='#b48e9a', nose='#bc8d98', mouth='#6f6970', whisker='#d6d5ce',
        eye='#d9bd65', eye_light='#ecdc9b', white='#f2eee4'),
    'cow': _coat('calico', name='奶牛猫', pattern='cow', group='纯色与双色',
        body='#f4f0e7', body_shadow='#e3ded4', face='#faf6ee', face_shadow='#ede7dc',
        arm='#f1ece3', paw='#f5efe4', tail='#343741', edge='#aba498', seam='#8d857b',
        ear='#d9a5ab', patch='#343741', eye='#b9d580', eye_light='#dcedac'),
    'white': _coat('calico', name='异瞳白猫', pattern='solid', group='纯色与双色',
        body='#f2eee8', body_shadow='#e3ded8', face='#fdfbf5', face_shadow='#eee9e3',
        arm='#f2ede7', paw='#faf6f0', tail='#ebe6df', edge='#b2aaa3', seam='#b3a69f',
        ear='#e6b9bf', nose='#cf9fa6', mouth='#a07f87', whisker='#b0a49f',
        eye='#84bddc', eye_light='#b5e0f2', eye_right='#ddbd64', eye_right_light='#f1dea0'),
    'siamese': _coat('ragdoll', name='暹罗', pattern='siamese', group='花色与重点色',
        body='#e4d5bc', body_shadow='#d2bfa5', face='#e9d9c1', face_shadow='#d8c5aa',
        arm='#dfcdb1', paw='#66524c', tail='#65514d', edge='#a68e78', seam='#d3bfa9',
        ear='#ad8583', nose='#463d40', mouth='#d9bdb9', whisker='#e1d2bf',
        point='#5d4b48', point_light='#80645a', eye='#7ab8e8', eye_light='#b8ddf4'),
    'tortie': _coat('black', name='玳瑁', pattern='tortie', group='花色与重点色',
        body='#3c3432', body_shadow='#2e2928', face='#443a35', face_shadow='#332d2b',
        arm='#3f3631', paw='#4b3e34', tail='#372e2b', edge='#635044', seam='#d3b398',
        ear='#b98e83', nose='#ba8b86', mouth='#c2a097', whisker='#dbc8b0',
        orange='#c48c51', orange_light='#dba56c', eye='#c1ca73', eye_light='#e2e5a2'),
})
