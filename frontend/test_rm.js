const React = require('react');
const ReactMarkdown = require('react-markdown');
const remarkGfm = require('remark-gfm');
const { renderToStaticMarkup } = require('react-dom/server');

const markdown = `- [x] Checked item
- [ ] Unchecked item
`;

const components = {
  li: ({ node, checked, className, children, ...props }) => {
    console.log("LI called. checked=", checked, "className=", className);
    let foundInputProps = null;
    const findCheckbox = (nodes) => {
      React.Children.forEach(nodes, (child) => {
        if (React.isValidElement(child)) {
          if (child.type === 'input' && child.props.type === 'checkbox') {
            foundInputProps = child.props;
          } else if (child.props && child.props.children) {
            findCheckbox(child.props.children);
          }
        }
      });
    };
    findCheckbox(children);
    console.log("Found input props:", foundInputProps);
    return React.createElement('li', {}, children);
  }
};

const el = React.createElement(ReactMarkdown, {
  remarkPlugins: [remarkGfm],
  components: components
}, markdown);

renderToStaticMarkup(el);
