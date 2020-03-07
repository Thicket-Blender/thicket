import hashlib
import json
import sys
import laubwerk as lbw


def md5sum(filename):
    md5 = hashlib.md5()
    with open(filename, mode='rb') as f:
        buf = f.read(4096)
        while buf:
            md5.update(buf)
            buf = f.read(4096)
    return md5.hexdigest()


def main(filename):
    p = lbw.load(filename)
    p_rec = {}

    plant = {}
    plant["name"] = p.name
    plant["md5"] = md5sum(filename)
    plant["default_model"] = p.default_model.name

    labels = {}
    p_labels = {}
    # Store only the first label per locale
    for l in p.labels.items():
        p_labels[l[0]] = l[1][0]
    labels[p.name] = p_labels

    models = {}
    i = 0
    for m in p.models:
        m_rec = {}
        seasons = []
        q_labels = {}
        for q in m.qualifiers:
            seasons.append(q)
            q_labels[q] = {}
            for q_lang in m.qualifier_labels[q].items():
                q_labels[q][q_lang[0]] = q_lang[1][0]
        labels.update(q_labels)
        m_rec["index"] = i
        m_rec["qualifiers"] = seasons
        m_rec["default_qualifier"] = m.default_qualifier
        models[m.name] = m_rec
        m_labels = {}
        # FIXME: highly redundant
        for l in m.labels.items():
            m_labels[l[0]] = l[1][0]
        labels[m.name] = m_labels
        i = i + 1
    plant["models"] = models

    p_rec["plant"] = plant
    p_rec["labels"] = labels

    print(json.dumps(p_rec))


if __name__ == "__main__":
    main(sys.argv[1])
