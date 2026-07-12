"""Sprint 23: siembra del catálogo CIE-10 odontológico (literal N del Form 033)."""

from django.db import migrations

CIE10_DENTAL = [
    ("K00", "Trastornos del desarrollo y de la erupción de los dientes"),
    ("K00.0", "Anodoncia"), ("K00.1", "Dientes supernumerarios"),
    ("K00.2", "Anomalías del tamaño y de la forma del diente"),
    ("K00.3", "Dientes moteados"), ("K00.4", "Alteraciones en la formación dentaria"),
    ("K00.5", "Alteraciones hereditarias de la estructura dentaria NCOP"),
    ("K00.6", "Alteraciones en la erupción dentaria"),
    ("K00.7", "Síndrome de la erupción dentaria"),
    ("K00.9", "Trastorno del desarrollo de los dientes, no especificado"),
    ("K01", "Dientes incluidos e impactados"),
    ("K01.0", "Dientes incluidos"), ("K01.1", "Dientes impactados"),
    ("K02", "Caries dental"),
    ("K02.0", "Caries limitada al esmalte"), ("K02.1", "Caries de la dentina"),
    ("K02.2", "Caries del cemento"), ("K02.3", "Caries dentaria detenida"),
    ("K02.4", "Odontoclasia"), ("K02.5", "Caries con exposición pulpar"),
    ("K02.8", "Otras caries dentales"), ("K02.9", "Caries dental, no especificada"),
    ("K03", "Otras enfermedades de los tejidos duros de los dientes"),
    ("K03.0", "Atrición excesiva de los dientes"), ("K03.1", "Abrasión de los dientes"),
    ("K03.2", "Erosión de los dientes"), ("K03.3", "Reabsorción patológica de los dientes"),
    ("K03.4", "Hipercementosis"), ("K03.5", "Anquilosis dental"),
    ("K03.6", "Depósitos [acreciones] en los dientes"),
    ("K03.7", "Cambios posteruptivos del color de los tejidos dentales duros"),
    ("K03.8", "Otras enfermedades especificadas de los tejidos duros de los dientes"),
    ("K03.9", "Enfermedad no especificada de los tejidos dentales duros"),
    ("K04", "Enfermedades de la pulpa y de los tejidos periapicales"),
    ("K04.0", "Pulpitis"), ("K04.1", "Necrosis de la pulpa"),
    ("K04.2", "Degeneración de la pulpa"),
    ("K04.3", "Formación anormal de tejido duro en la pulpa"),
    ("K04.4", "Periodontitis apical aguda originada en la pulpa"),
    ("K04.5", "Periodontitis apical crónica"), ("K04.6", "Absceso periapical con fístula"),
    ("K04.7", "Absceso periapical sin fístula"), ("K04.8", "Quiste radicular"),
    ("K04.9", "Otras enfermedades de la pulpa y del tejido periapical"),
    ("K05", "Gingivitis y enfermedades periodontales"),
    ("K05.0", "Gingivitis aguda"), ("K05.1", "Gingivitis crónica"),
    ("K05.2", "Periodontitis aguda"), ("K05.3", "Periodontitis crónica"),
    ("K05.4", "Periodontosis"), ("K05.5", "Otras enfermedades periodontales"),
    ("K05.6", "Enfermedad del periodonto, no especificada"),
    ("K06", "Otros trastornos de la encía y de la zona edéntula"),
    ("K06.0", "Retracción gingival"), ("K06.1", "Hiperplasia gingival"),
    ("K06.8", "Otros trastornos especificados de la encía y de la zona edéntula"),
    ("K06.9", "Trastorno no especificado de la encía y de la zona edéntula"),
    ("K07", "Anomalías dentofaciales [incluso la maloclusión]"),
    ("K07.0", "Anomalías evidentes del tamaño de los maxilares"),
    ("K07.1", "Anomalías de la relación maxilobasilar"),
    ("K07.2", "Anomalías de la relación entre los arcos dentarios"),
    ("K07.3", "Anomalías de la posición del diente"),
    ("K07.4", "Maloclusión de tipo no especificado"),
    ("K07.5", "Anomalías dentofaciales funcionales"),
    ("K07.6", "Trastornos de la articulación temporomandibular"),
    ("K08", "Otros trastornos de los dientes y de sus estructuras de sostén"),
    ("K08.0", "Exfoliación de los dientes debida a causas sistémicas"),
    ("K08.1", "Pérdida de dientes por accidente, extracción o enf. periodontal local"),
    ("K08.2", "Atrofia del reborde alveolar desdentado"),
    ("K08.3", "Raíz dental retenida"),
    ("K08.8", "Otros trastornos de los dientes y de sus estructuras de sostén"),
    ("K08.9", "Trastorno de los dientes y de sus estructuras de sostén, no especificado"),
    ("K09", "Quistes de la región bucal, no clasificados en otra parte"),
    ("K10", "Otras enfermedades de los maxilares"),
    ("K11", "Enfermedades de las glándulas salivales"),
    ("K12", "Estomatitis y lesiones afines"),
    ("K12.0", "Estomatitis aftosa recurrente"), ("K12.1", "Otras formas de estomatitis"),
    ("K12.2", "Celulitis y absceso de boca"),
    ("K13", "Otras enfermedades de los labios y de la mucosa bucal"),
    ("K13.0", "Enfermedades de los labios"),
    ("K13.7", "Otras lesiones de la mucosa bucal"),
    ("K14", "Enfermedades de la lengua"),
    ("K14.0", "Glositis"), ("K14.1", "Lengua geográfica"),
    ("S02.5", "Fractura de los dientes"),
    ("S03.2", "Luxación de diente"),
    ("Z01.2", "Examen odontológico"),
    ("Z29.8", "Aplicación de sellantes / flúor (medida profiláctica)"),
]


def seed(apps, schema_editor):
    Cie10 = apps.get_model("clinical", "Cie10")
    for code, description in CIE10_DENTAL:
        Cie10.objects.get_or_create(code=code, defaults={"description": description})


def unseed(apps, schema_editor):
    apps.get_model("clinical", "Cie10").objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [("clinical", "0007_form033")]
    operations = [migrations.RunPython(seed, unseed)]
