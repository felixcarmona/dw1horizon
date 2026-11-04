"""Simplified Chinese wording for baked labels and scene artwork."""
UI = dict(zip(
    ['PERFIL','ESTADO','ATRIBUTOS','PESO','TIPO','OBJETOS','JUGADOR','ALABAR','REÑIR','DORMIR','PESCAR',
     'NOMBRE','ESPECIE','EDAD','ACTIVO','ESPECIAL','FELICIDAD','VELOCIDAD','INTELECTO','RAPIDEZ',
     'POTENCIA','ALC.','ALCANCE','EFECTO','DATOS TÉC.','OBJETO','PRECIO','TÍTULO','LUGAR','PUNTOS','CANT.','Nº',
     'FUEGO','COMBATE','AIRE','TIERRA','HIELO','MECA','MUGRE'],
    ['资料','状态','能力','体重','属性','道具','玩家','表扬','训斥','睡觉','钓鱼','名字','种族','年龄','作息','擅长',
     '心情','速度','智力','速度','威力','范围','范围','效果','招式资料','道具','价格','名称','地点','点数','数量','编号',
     '火焰','格斗','空气','大地','冰雪','机械','污物']))
SIGNS = {
 'betl02':'竞技场','frzl06':'冰山海滩 / 迷雾树林','gcan09':'黑白商店 / 应有尽有',
 'gias06b':'回收与卡片 / 回收卡片商店 / 特价','mayo01_2':'全景山',
 'mayo10':'钓鱼守则 / 一、此地属于大家，请勿乱扔垃圾。 / 二、切勿过度捕捞。 / 哼！我才不管！',
 'mayo11':'钓鱼守则 / 一、此地属于大家，请勿乱扔垃圾。 / 二、切勿过度捕捞。 / 哼！我才不管！',
 'omoc08':'本帮到此一游！','room02':'欢迎光临','trai00':'战斗课堂','twnb_open':'营业中','twnb_tool':'道具店',
 'audit-0':'接待处','audit-1':'报名处','audit-2':'报名处','audit-3':'候场室','audit-4':'冰上游戏',
 'audit-5':'观众席入口','audit-7':'道具寄存处','audit-8':'道具寄存处','audit-9':'餐厅','audit-10':'道具',
 'audit-13':'钻头隧道','mayo11_ogre':'恶鬼隧道','audit-14':'绿色 / 健身房','audit-22':'当心！ / 落石！',
 'audit-24':'公共厕所','audit-27':'垃圾区','audit-28':'好！！','audit-29':'好！！','audit-30':'失败','audit-31':'危险',
}
CUPS = {
 'AN':('野兽','杯','半兽型数码宝贝，快来参加！'), 'BT':('甲虫','杯','快来参加甲虫杯！'),
 'CO':('酷寒','杯','谁是最酷的数码宝贝？快来参加酷寒杯！'), 'DT':('污秽','杯','哎呀！对不起……满身脏兮兮！快来参加！'),
 'DY':('恐龙','杯','快来参加恐龙杯！'), 'FR':('烈火','杯','火焰数码宝贝，快来参加！'),
 'GP':('格斗','杯','谁是最强的格斗家？'), 'HU':('人型','杯','半人型数码宝贝，快来参加！'),
 'MT':('金属','杯','铠甲、机械、金属……谁能夺冠？'), 'NT':('自然','杯','巨虫来袭！草木行动！一起唱响自然杯！'),
 'TW':('雷风','杯','电流、翅膀、多尾、风与雷'), 'WI':('羽翼','杯','快来参加羽翼杯！'),
}
CAPTIONS = ('数码宝贝竞技场', '公开赛', '等级 ')
BATTLE = '战斗！'
SMALL = dict(partner='搭档', push='按下', finish='必杀！', life='生命', start='按START键', time='时间到！', vs='对战模式',
             battle='战斗模式', arena='选择场地', fight='战斗')


def texts():
    yield from UI.values()
    yield from SIGNS.values()
    for parts in CUPS.values():yield from parts
    yield from CAPTIONS
    yield BATTLE
    yield from SMALL.values()
