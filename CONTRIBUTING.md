Contributions are welcome.

When preparing your changes and your commit messages, please ensure to break up your changes into independent functional changes. Be sure to document each change with short subject line followed by a longer description of the problem and how you intended to fix it. Finally, sign off your commit messages with "Signed-off-by: Your Name \<email address\>" (see http://developercertificate.org).

For example:

```
Implement diffuse color

Use the material front side diffuseColor for the diffuse color.

For proxy models, use the foliage and wood color API to set the diffuse
color. According to Laubwerk, the matID[0] of -1 is used for foliage on
proxy models.

Signed-off-by: Darren Hart <dvhart@infradead.org>

```

You can automatically add your Signed-off-by with `git commit -s`.

To submit a contribution, follow the traditional GitHub workflow: https://guides.github.com/activities/forking/
