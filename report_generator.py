from jinja2 import Template


def generate_html(report):

    template = """
    <html>
    <head>
    <title>Jenkins Environment Validation</title>
    <style>

    body { font-family: Arial; }

    table {
        border-collapse: collapse;
        width: 80%;
    }

    th, td {
        border:1px solid #ddd;
        padding:8px;
    }

    th {
        background-color:#333;
        color:white;
    }

    .pass { color:green; font-weight:bold }
    .fail { color:red; font-weight:bold }

    </style>
    </head>

    <body>

    <h2>Jenkins Environment Validation</h2>

    <p><b>Node:</b> {{node}}</p>
    <p><b>Environment:</b> {{environment}}</p>

    <table>

    <tr>
    <th>Check</th>
    <th>Status</th>
    <th>Message</th>
    </tr>

    {% for r in results %}

    <tr>

    <td>{{r.name}}</td>

    <td class="{{ 'pass' if r.success else 'fail' }}">
    {{ 'PASS' if r.success else 'FAIL' }}
    </td>

    <td>{{r.message}}</td>

    </tr>

    {% endfor %}

    </table>

    </body>
    </html>
    """

    html = Template(template).render(**report)

    with open("reports/report.html","w") as f:
        f.write(html)