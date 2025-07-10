from django.shortcuts import render, redirect, reverse, get_object_or_404
from django.views.generic.list import ListView
from django.views.generic.detail import DetailView
from django.views import View
from django.contrib import messages
from . import models
from perfil.models import Perfil


class CarrinhoMixin:
    def _get_carrinho(self):
        if "carrinho" not in self.request.session:
            self.request.session["carrinho"] = {}
            self.request.session.save()
        return self.request.session["carrinho"]

    def _save_carrinho(self, carrinho):
        self.request.session["carrinho"] = carrinho
        self.request.session.save()


class ListaProdutos(ListView):
    model = models.Produto
    template_name = "produto/lista.html"
    context_object_name = "produtos"
    paginate_by = 10


class DetalheProduto(DetailView):
    model = models.Produto
    template_name = "produto/detalhe.html"
    context_object_name = "produto"
    slug_url_kwarg = "slug"


class AdicionarAoCarrinho(CarrinhoMixin, View):
    def get(self, *args, **kwargs):
        http_referer = self.request.META.get("HTTP_REFERER", reverse("produto:lista"))
        variacao_id = self.request.GET.get("vid")

        if not variacao_id:
            messages.error(self.request, "Variação do produto não especificada.")
            return redirect(http_referer)

        variacao = get_object_or_404(models.Variacao, id=variacao_id)
        produto = variacao.produto

        if variacao.estoque < 1:
            messages.error(self.request, "Estoque insuficiente para este item.")
            return redirect(http_referer)

        item_carrinho_data = {
            "produto_id": produto.id,
            "produto_nome": produto.nome,
            "variacao_nome": variacao.nome or "",
            "variacao_id": str(variacao.id),
            "preco_unitario": float(variacao.preco),
            "preco_unitario_promocional": float(variacao.preco_promocional),
            "slug": produto.slug,
            "imagem": produto.imagem.name if produto.imagem else "",
        }

        carrinho = self._get_carrinho()

        if item_carrinho_data["variacao_id"] in carrinho:
            quantidade_no_carrinho = (
                carrinho[item_carrinho_data["variacao_id"]]["quantidade"] + 1
            )

            if variacao.estoque < quantidade_no_carrinho:
                messages.warning(
                    self.request,
                    f"Estoque insuficiente para {quantidade_no_carrinho}x do "
                    f'produto "{produto.nome} {variacao.nome}". '
                    f"Adicionamos {variacao.estoque}x no seu carrinho.",
                )
                quantidade_no_carrinho = variacao.estoque

            carrinho[item_carrinho_data["variacao_id"]][
                "quantidade"
            ] = quantidade_no_carrinho
            carrinho[item_carrinho_data["variacao_id"]]["preco_quantitativo"] = (
                item_carrinho_data["preco_unitario"] * quantidade_no_carrinho
            )
            carrinho[item_carrinho_data["variacao_id"]][
                "preco_quantitativo_promocional"
            ] = (
                item_carrinho_data["preco_unitario_promocional"]
                * quantidade_no_carrinho
            )

            if quantidade_no_carrinho > (
                carrinho[item_carrinho_data["variacao_id"]].get("quantidade") or 0
            ):
                messages.success(
                    self.request,
                    f'Produto "{produto.nome} {variacao.nome}" atualizado para {quantidade_no_carrinho}x no carrinho.',
                )
        else:
            item_carrinho_data["quantidade"] = 1
            item_carrinho_data["preco_quantitativo"] = item_carrinho_data[
                "preco_unitario"
            ]
            item_carrinho_data["preco_quantitativo_promocional"] = item_carrinho_data[
                "preco_unitario_promocional"
            ]

            carrinho[item_carrinho_data["variacao_id"]] = item_carrinho_data

            messages.success(
                self.request,
                f'Produto "{produto.nome} {variacao.nome}" adicionado ao seu carrinho.',
            )

        self._save_carrinho(carrinho)
        return redirect(http_referer)


class RemoverDoCarrinho(CarrinhoMixin, View):
    def get(self, *args, **kwargs):
        http_referer = self.request.META.get("HTTP_REFERER", reverse("produto:lista"))
        variacao_id = self.request.GET.get("vid")

        if not variacao_id:
            messages.error(
                self.request, "Variação do produto não especificada para remoção."
            )
            return redirect(http_referer)

        carrinho = self._get_carrinho()

        if str(variacao_id) not in carrinho:
            messages.warning(self.request, "Item não encontrado no carrinho.")
            return redirect(http_referer)

        item_removido = carrinho.pop(str(variacao_id))

        messages.success(
            self.request,
            f'Produto "{item_removido["produto_nome"]} {item_removido["variacao_nome"]}" '
            f"removido do seu carrinho.",
        )

        self._save_carrinho(carrinho)
        return redirect(http_referer)


class Carrinho(CarrinhoMixin, View):
    def get(self, *args, **kwargs):
        contexto = {"carrinho": self._get_carrinho()}
        return render(self.request, "produto/carrinho.html", contexto)


class ResumoDaCompra(CarrinhoMixin, View):
    def get(self, *args, **kwargs):
        if not self.request.user.is_authenticated:
            messages.info(
                self.request, "Você precisa estar logado para finalizar a compra."
            )
            return redirect("perfil:criar")

        perfil = Perfil.objects.filter(usuario=self.request.user).first()
        if not perfil:
            messages.warning(
                self.request,
                "Você precisa completar seu perfil para prosseguir com a compra.",
            )
            return redirect("perfil:criar")

        carrinho = self._get_carrinho()
        if not carrinho:
            messages.warning(self.request, "Seu carrinho está vazio.")
            return redirect("produto:lista")

        contexto = {
            "usuario": self.request.user,
            "perfil": perfil,
            "carrinho": carrinho,
        }

        return render(self.request, "produto/resumodacompra.html", contexto)
